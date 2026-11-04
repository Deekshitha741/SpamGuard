"""Check the model works and that SPAM_LABEL is the right one.

Usage:  python test_model.py
Spam samples should score HIGH (near 1.0), normal ones LOW (near 0.0).
If it's the other way round, change SPAM_LABEL in model.py.
"""
from model import MODEL_NAME, SPAM_LABEL, _get_classifier, spam_scores

print("Model:", MODEL_NAME)
print("Labels:", _get_classifier().model.config.id2label)
print("Treating as spam:", SPAM_LABEL, "\n")

samples = [
    ("SPAM?", "CONGRATULATIONS!!! You have WON $1,000,000. Click here now to claim your free prize!!!"),
    ("SPAM?", "Cheap meds online, no prescription needed. Buy viagra now, limited offer!!!"),
    ("NORMAL?", "Hi team, the meeting is moved to 3 PM tomorrow. Please review the attached notes."),
    ("NORMAL?", "Can you send me the report by Friday? Thanks, Priya"),
]
scores = spam_scores([text for _, text in samples])
for (kind, text), score in zip(samples, scores):
    print(f"{kind:8} spam score {score:.3f}  |  {text[:60]}")
