"""Readability metric helpers — pure functions, no external dependencies beyond stdlib."""
import re


def count_sentences(text: str) -> int:
    """Count sentences by splitting on terminal punctuation (. ! ?)."""
    # Split on sentence-ending punctuation followed by whitespace or end-of-string
    sentences = re.split(r'[.!?]+(?:\s|$)', text.strip())
    # Filter out empty strings produced by the split
    return max(1, len([s for s in sentences if s.strip()]))


def count_syllables(word: str) -> int:
    """Estimate syllable count using a vowel-counting heuristic.

    Rules applied:
    - Count vowel groups (consecutive vowels count as one syllable).
    - Subtract silent trailing 'e'.
    - Every word has at least 1 syllable.
    """
    word = word.lower().strip(".,!?;:\"'()-")
    if not word:
        return 0

    vowels = "aeiouy"
    count = 0
    prev_vowel = False
    for ch in word:
        is_vowel = ch in vowels
        if is_vowel and not prev_vowel:
            count += 1
        prev_vowel = is_vowel

    # Subtract silent trailing 'e' for words longer than 2 characters
    if word.endswith('e') and len(word) > 2:
        count = max(1, count - 1)

    return max(1, count)


def flesch_reading_ease(text: str) -> float:
    """Compute the Flesch Reading Ease score for *text*.

    Formula: 206.835 - 1.015 * (words/sentences) - 84.6 * (syllables/words)

    Higher score = easier to read (90–100: very easy, 0–30: very difficult).
    """
    words = text.split()
    num_words = len(words)
    if num_words == 0:
        return 0.0

    num_sentences = count_sentences(text)
    num_syllables = sum(count_syllables(w) for w in words)

    avg_sentence_length = num_words / num_sentences
    avg_syllables_per_word = num_syllables / num_words

    score = 206.835 - 1.015 * avg_sentence_length - 84.6 * avg_syllables_per_word
    return round(score, 2)


def average_sentence_length(text: str) -> float:
    """Return average number of words per sentence."""
    words = text.split()
    sentences = count_sentences(text)
    if sentences == 0:
        return 0.0
    return round(len(words) / sentences, 2)


def paragraph_count(text: str) -> int:
    """Count non-empty paragraphs (blocks separated by blank lines)."""
    blocks = re.split(r'\n{2,}', text.strip())
    return len([b for b in blocks if b.strip()])
