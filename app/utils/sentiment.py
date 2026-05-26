from textblob import TextBlob


def analyze_sentiment(text: str) -> dict:
    """
    يحلل نص ويرجع:
    - sentiment: "positive" | "negative" | "neutral"
    - score: من -1.0 (سلبي جداً) إلى 1.0 (إيجابي جداً)
    """

    blob  = TextBlob(text)
    score = blob.sentiment.polarity  # -1.0 to 1.0

    if score > 0.1:
        sentiment = "positive"
    elif score < -0.1:
        sentiment = "negative"
    else:
        sentiment = "neutral"

    return {
        "sentiment": sentiment,
        "score":     round(score, 4)
    }