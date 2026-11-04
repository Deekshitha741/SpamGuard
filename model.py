"""Step 3: load a pre-trained spam model and score text with it."""
from transformers import pipeline

# A tiny (4M parameter) BERT fine-tuned on the Enron email spam dataset.
# To try another model, just change this name.
MODEL_NAME = "mrm8488/bert-tiny-finetuned-enron-spam-detection"

# Which output label means "spam". Run test_model.py to confirm this!
SPAM_LABEL = "LABEL_1"

_classifier = None


def _get_classifier():
    """Load the model once, then reuse it (loading is slow)."""
    global _classifier
    if _classifier is None:
        _classifier = pipeline("text-classification", model=MODEL_NAME, top_k=None)
    return _classifier


def build_text(mail):
    """Combine subject + body into one string, capped in length."""
    text = f"{mail['subject']}. {mail['text']}"
    return text[:2000]


def spam_scores(texts):
    """Return a list of spam probabilities (0.0 to 1.0), one per text."""
    results = _get_classifier()(
        list(texts), truncation=True, max_length=256, batch_size=8
    )
    scores = []
    for labels in results:
        by_label = {item["label"]: item["score"] for item in labels}
        scores.append(by_label.get(SPAM_LABEL, 0.0))
    return scores
