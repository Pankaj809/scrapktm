"""Deterministic Preeti-font (legacy Nepali TTF) to Unicode Devanagari repair.

Preeti maps Devanagari to Latin-1 code points for rendering; when such a PDF has
no ToUnicode CMap, text extraction yields Latin gibberish like
``sf7df8f}“ dxfgu/kflnsf`` which is really ``काठमाडौं महानगरपालिका``.

This module implements the standard Preeti glyph-substitution table plus the two
post-processing rules a byte-substitution alone cannot handle:
  1. short-i matra reordering: Preeti types ``ि`` (glyph ``l``) *before* its
     consonant; Unicode places it *after*.
  2. reph reordering: Preeti ``{`` (``र्``) is typed before the consonant it caps.

The map is not lossless for every rare conjunct (documented limitation), so
``repair_stats`` reports the measured Devanagari-validity of the output rather
than assuming perfection.
"""

from __future__ import annotations

# Multi-character sequences MUST be substituted before single characters.
# Ordered longest-first at apply time.
PREETI_MAP = {
    # vowel-sign compounds
    "f}": "ौ", "f]": "ो",
    # independent vowels
    "cf}": "औ", "cf]": "ओ", "cf": "आ", "O{": "ई", "P]": "ऐ", "P": "ए",
    "pm": "ऊ", "p": "उ", "C": "ऋ", "c": "अ", "O": "इ",
    # common consonant clusters / special glyphs
    "km": "फ", "Km": "फ", "if": "ष", "If": "क्ष", "1": "ज्ञ", "@": "२",
    "0f": "णा", "~f": "ञ", "6f": "टा",
    "s|": "क्र", "k|": "प्र", "t|": "त्र", "b|": "द्र", "u|": "ग्र", "3|": "घ्र",
    "z|": "श्र", "d|": "म्र", "h|": "ज्र", "j|": "व्र", "g|": "न्र",
    ":": "स्", "S": "क्", "km|": "फ्र",
}

# Single-character table (consonants, matras, digits, punctuation).
PREETI_SINGLE = {
    ")": "०", "!": "१", "@": "२", "#": "३", "$": "४", "%": "५",
    "^": "६", "&": "७", "*": "८", "(": "९",
    "s": "क", "v": "ख", "u": "ग", "3": "घ", "ª": "ङ",
    "r": "च", "5": "छ", "h": "ज", "´": "ञ",
    "6": "ट", "7": "ठ", "8": "ड", "9": "ढ", "0": "ण",
    "t": "त", "y": "थ", "b": "द", "w": "ध", "g": "न",
    "k": "प", "a": "ब", "e": "भ", "d": "म",
    "o": "य", "/": "र", "n": "ल", "j": "व",
    "z": "श", ";": "स", "x": "ह",
    "If": "क्ष", "q": "त्र", "1": "ज्ञ",
    # uppercase Preeti letters are half (halant-terminated) consonants
    "S": "क्", "V": "ख्", "U": "ग्", "H": "ज्", "6f": "टा",
    "T": "त्", "Y": "थ्", "W": "ध्", "G": "न्", "K": "प्",
    "A": "ब्", "E": "भ्", "D": "म्", "J": "व्", "Z": "श्",
    "R": "च्", "N": "ल्", "B": "न्न",
    # matras and signs
    "f": "ा", "l": "ि", "L": "ी", "'": "ु", "\"": "ू",
    "]": "े", "}": "ौ", "]": "े", "[": "ै",
    "F": "ँ", "+": "ं", "M": "ः", "±": "ं",
    "?": "र", "|": "्र", "\\": "्",
    "{": "र्",  # reph, reordered in post-processing
    "å": "द्व", "Í": "र्", "“": "ं", "”": "ं", "‘": "ऽ",
    "=": "।", ".": ".", ",": ",",
}

REPH = "﷐"  # private placeholder for reph during reordering


def _apply_map(text: str) -> str:
    out = []
    i = 0
    n = len(text)
    multis = sorted(PREETI_MAP, key=len, reverse=True)
    while i < n:
        matched = False
        for seq in multis:
            if text.startswith(seq, i):
                out.append(PREETI_MAP[seq])
                i += len(seq)
                matched = True
                break
        if matched:
            continue
        ch = text[i]
        if ch == "{":
            out.append(REPH)
        else:
            out.append(PREETI_SINGLE.get(ch, ch))
        i += 1
    return "".join(out)


_DEV_CONS = set("कखगघङचछजझञटठडढणतथदधनपफबभमयरलवशषसह")


def _reorder_i_matra(text: str) -> str:
    """Move ``ि`` (U+093F) that precedes a consonant to just after it."""
    chars = list(text)
    out = []
    i = 0
    while i < len(chars):
        if chars[i] == "ि" and i + 1 < len(chars) and chars[i + 1] in _DEV_CONS:
            # find end of the following consonant cluster (cons + optional halant+cons)
            j = i + 1
            while j + 1 < len(chars) and chars[j + 1] == "्":
                j += 2 if j + 2 < len(chars) else 1
            out.extend(chars[i + 1:j + 1])
            out.append("ि")
            i = j + 1
        else:
            out.append(chars[i])
            i += 1
    return "".join(out)


def _reorder_reph(text: str) -> str:
    """Place reph (र्) *before* the preceding consonant it caps.

    Preeti types the reph glyph after the consonant cluster (e.g. ``jif{`` =
    व ष र-reph), but Devanagari renders र् before that consonant: वर्ष.
    """
    out = []
    for ch in text:
        if ch == REPH:
            # walk back to the last consonant in the output and insert र् before it
            p = len(out) - 1
            while p >= 0 and out[p] not in _DEV_CONS:
                p -= 1
            if p >= 0:
                out.insert(p, "्")
                out.insert(p, "र")
            else:
                out.extend(["र", "्"])
        else:
            out.append(ch)
    return "".join(out)


def convert(text: str) -> str:
    """Convert Preeti-encoded Latin text to Unicode Devanagari (best-effort)."""
    t = _apply_map(text)
    t = _reorder_i_matra(t)
    t = _reorder_reph(t)
    return t.replace(REPH, "र्")


def devanagari_ratio(text: str) -> float:
    dev = sum(1 for ch in text if "ऀ" <= ch <= "ॿ")
    lat = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    tot = dev + lat
    return (dev / tot) if tot else 0.0


if __name__ == "__main__":
    samples = [
        ("sf7df8f}“ dxfgu/kflnsf", "काठमाडौं महानगरपालिका"),
        (":yfgLo /fhkq", "स्थानीय राजपत्र"),
        ("Joj;fo s/", "व्यवसाय कर"),
    ]
    for src, expect in samples:
        got = convert(src)
        print(f"IN : {src}")
        print(f"OUT: {got}")
        print(f"EXP: {expect}   dev%={devanagari_ratio(got)*100:.0f}\n")
