# SPDX-License-Identifier: GPL-3.0-or-later
"""Title matching for SoundCloud uploads: scripts, variants and versions."""

import re
import unicodedata

from unidecode import unidecode

from ...matching import normalize, similarity
from ...scoring import DEFAULT_SOUNDCLOUD_SCORING
from .search import normalize_title_text

# Words that mark a different version of a song. A result containing one of
# them is only accepted when the requested title contains it as well.
VERSION_MARKERS = (
    "remix",
    "rmx",
    "bootleg",
    "mashup",
    "cover",
    "karaoke",
    "instrumental",
    "nightcore",
    "sped up",
    "slowed",
    "reverb",
    "live",
    "concert",
    "acoustic",
    "piano version",
    "8d audio",
)

def _transliterate(text) -> str:
    """Latin-script form with the apostrophes Unidecode adds removed."""
    return unidecode(text or "").replace("'", "")


def _cross_script_similarity(a: str, b: str) -> float:
    return max(
        similarity(a, b),
        similarity(_transliterate(a), _transliterate(b)),
    )


def _contains_artist(artist: str, text: str) -> bool:
    if not artist or not text:
        return False

    forms = zip(
        (artist, _transliterate(artist)),
        (text, _transliterate(text)),
        strict=False,
    )

    for artist_form, text_form in forms:
        normalized_artist = normalize(artist_form)
        normalized_text = normalize(text_form)

        if normalized_artist and normalized_artist in normalized_text:
            return True

    return False


def _title_variants(candidate):
    """Return the plausible song-title forms of a SoundCloud upload.

    Uploads are commonly named ``Artist - Track``, ``Artist - Track (Official
    Audio)`` or just ``Track``. Comparing every form avoids penalizing a
    correct upload for the extra artist prefix.
    """
    raw = candidate.get("raw_title") or candidate.get("title") or ""
    track = candidate.get("title") or ""
    variants = []

    for value in (track, raw):
        value = normalize_title_text(value)

        if value and value not in variants:
            variants.append(value)

        if " - " in value:
            remainder = value.split(" - ", 1)[1].strip()

            if remainder and remainder not in variants:
                variants.append(remainder)

        if " – " in value:
            remainder = value.split(" – ", 1)[1].strip()

            if remainder and remainder not in variants:
                variants.append(remainder)

    return variants


def _candidate_artist_names(candidate):
    names = []

    for name in [candidate.get("artist"), *(candidate.get("artists") or [])]:
        if name and name not in names:
            names.append(name)

    uploader = candidate.get("uploader")

    if uploader and uploader not in names:
        names.append(uploader)

    # ``Artist - Track`` also carries artist evidence in the title prefix.
    raw = candidate.get("raw_title") or candidate.get("title") or ""

    for separator in (" - ", " – "):
        if separator in raw:
            prefix = raw.split(separator, 1)[0].strip()

            if prefix and prefix not in names:
                names.append(prefix)

            break

    return names


def _tokens(text):
    return normalize(text).split()


def _strip_artist_prefix(tokens, artist):
    """Drop leading tokens that belong to the artist name.

    ``Artist - Song`` and ``Artist Song`` both name the artist before the
    song. Those tokens are not evidence of a different title. Both the
    original script and the Latin transliteration are considered, so a Latin
    upload of a Cyrillic artist still has its prefix removed.
    """
    artist_tokens = set(_tokens(artist)) | set(_tokens(_transliterate(artist)))

    if not artist_tokens:
        return tokens

    index = 0

    while index < len(tokens) and tokens[index] in artist_tokens:
        index += 1

    return tokens[index:]


def _contiguous_index(haystack, needle):
    if not needle or len(needle) > len(haystack):
        return None

    for start in range(len(haystack) - len(needle) + 1):
        if haystack[start:start + len(needle)] == needle:
            return start

    return None


def _fuzzy_window(needle, haystack, scoring=DEFAULT_SOUNDCLOUD_SCORING):
    """Find the best same-length window of ``haystack`` similar to ``needle``.

    Used for transliteration variance: "gorbachiov" and "gorbachev" are the
    same title, but neither the tokens nor a naive similarity of the whole
    upload title line up. Returns ``(index, score)`` or None.
    """
    threshold = scoring.fuzzy_window_threshold

    if not needle or not haystack or len(needle) > len(haystack):
        return None

    best = None

    for start in range(len(haystack) - len(needle) + 1):
        window = " ".join(haystack[start:start + len(needle)])
        score = similarity(" ".join(needle), window)

        if score >= threshold and (best is None or score > best[1]):
            best = (start, score)

    return best


def _align_variant(variant, title, artist):
    """Find the title words inside a variant, or explain that they are absent.

    Returns ``(expected, variant_tokens, ratio, start)`` where ``start`` is
    None when the words are not contiguous.
    """
    expected = _tokens(title)

    if not expected:
        return None

    variant_tokens = _strip_artist_prefix(_tokens(variant), artist)
    # The Latin form catches a Latin-only upload of a Cyrillic title (and
    # the reverse), where no original-script token can ever match.
    expected_latin = _tokens(_transliterate(title))
    variant_latin = _strip_artist_prefix(
        _tokens(_transliterate(variant)),
        artist,
    )

    if not variant_tokens and not variant_latin:
        return None

    ratio = _cross_script_similarity(title, variant)
    start = _contiguous_index(variant_tokens, expected)

    if start is None and expected_latin:
        latin_start = _contiguous_index(variant_latin, expected_latin)

        if latin_start is not None:
            start = latin_start
            expected = expected_latin
            variant_tokens = variant_latin

    if start is None:
        # Title words can transliterate differently ("Горбачёв" becomes
        # "gorbachiov" while an uploader typed "gorbachev"). Slide a window
        # over the Latin tokens and accept a close one.
        fuzzy = _fuzzy_window(expected_latin, variant_latin)

        if fuzzy is not None:
            start, score = fuzzy
            expected = expected_latin
            variant_tokens = variant_latin
            ratio = max(ratio, score)

    return expected, variant_tokens, ratio, start


def _out_of_order_score(expected, variant_tokens, ratio, scoring):
    """Score a variant whose title words are present but not contiguous."""
    expected = set(expected)
    variant_set = set(variant_tokens)
    overlap = len(expected & variant_set)

    if overlap == 0:
        return 0.0

    recall = overlap / len(expected)
    precision = overlap / len(variant_set)
    f1 = (
        2 * recall * precision / (recall + precision)
        if recall + precision
        else 0.0
    )
    return max(ratio, f1) * scoring.ordered_words_discount


def _aligned_score(start, expected, variant_tokens, title, ratio, scoring):
    """Score a variant where the title is a contiguous token run."""
    if start > 0:
        # Words before the title: "Another Song" is not "Song".
        return ratio * scoring.leading_words_penalty

    trailing = len(variant_tokens) - (start + len(expected))

    if trailing > scoring.trailing_words_limit:
        return ratio * scoring.trailing_words_penalty

    # The title is a contiguous prefix. Upload suffixes ("- Kissvk.com",
    # "[HQ]") are common and, across scripts, drag the raw similarity down
    # even though the song itself matches exactly. Comparing the matched
    # prefix avoids that.
    prefix = " ".join(variant_tokens[start:start + len(expected)])
    return max(ratio, _cross_script_similarity(title, prefix))


def _title_variant_score(variant, title, artist, scoring=DEFAULT_SOUNDCLOUD_SCORING):
    """Compare one title variant, penalizing words the song does not have.

    A shared word is not enough: ``Artist - Another Song`` is a different
    song from ``Song`` even though it contains the title. Extra words after
    the title are common upload suffixes (``- Kissvk.com``, ``[HQ]``), while
    extra words *before* it usually mean another song, so only the leading
    case is penalized.
    """
    aligned = _align_variant(variant, title, artist)

    if aligned is None:
        return 0.0

    expected, variant_tokens, ratio, start = aligned

    if start is None and _transliterate(title) != title:
        # A Latin-only upload of a Cyrillic title (or the reverse) has no
        # shared tokens, but a high transliterated similarity is still good
        # evidence. The floor keeps an unrelated same-script title out.
        if ratio >= scoring.latin_similarity_floor:
            return ratio

    if start is None:
        return _out_of_order_score(expected, variant_tokens, ratio, scoring)

    return _aligned_score(start, expected, variant_tokens, title, ratio, scoring)


def _title_score(candidate, title, artist="", scoring=DEFAULT_SOUNDCLOUD_SCORING):
    variants = _title_variants(candidate)

    if not variants:
        return 0.0

    return max(
        _title_variant_score(variant, title, artist, scoring)
        for variant in variants
    )


def _version_markers(text):
    """Return the version markers present in raw text.

    ``matching.normalize`` exists for similarity and deliberately removes
    noise brackets such as ``(live)``. Markers must survive that removal, so
    this uses a light normalization that only lowercases and folds
    punctuation into spaces, leaving every word visible.
    """
    text = unicodedata.normalize("NFC", text or "").lower()
    text = text.replace("ё", "е")
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    normalized = f" {text} "
    found = set()

    for marker in VERSION_MARKERS:
        if f" {marker} " in normalized:
            found.add(marker)

    return found


def is_version_mismatch(candidate, title):
    """Whether the upload is a remix, cover, live take and so on.

    A marker in the requested title is intentional: asking for a remix must
    still find the remix. Markers that only exist on the candidate side mean
    it is a different recording.
    """
    candidate_text = " ".join(
        [
            candidate.get("raw_title") or "",
            candidate.get("title") or "",
        ]
    )
    requested = _version_markers(title or "")
    present = _version_markers(candidate_text)

    return bool(present - requested)
