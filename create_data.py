#!/usr/bin/env python3
"""
Create simple text data for transformer language model training.
"""
import random

# Simple sentences for training
sentences = [
    "The cat sat on the mat.",
    "A dog barked at the moon.",
    "Birds fly in the sky.",
    "Fish swim in the water.",
    "The sun shines brightly.",
    "Rain falls from clouds.",
    "Children play in the park.",
    "Books contain knowledge.",
    "Computers process information.",
    "Language models learn patterns.",
    "Neural networks have layers.",
    "Training requires data.",
    "Testing evaluates performance.",
    "Loss decreases with training.",
    "Accuracy improves over time.",
    "Transformers use attention.",
    "Tokens represent words.",
    "Embeddings capture meaning.",
    "Parameters get updated.",
    "Gradients guide learning.",
]

# Create a corpus by repeating sentences
corpus = []
for _ in range(100):  # 100 repetitions for enough training data
    corpus.extend(sentences)

# Shuffle the corpus
random.shuffle(corpus)

# Write to file
with open("training_data.txt", "w") as f:
    for sentence in corpus:
        f.write(sentence + "\n")

print(f"Created training_data.txt with {len(corpus)} sentences")
print(f"Total characters: {sum(len(s) for s in corpus)}")
print("Sample sentences:")
for i in range(5):
    print(f"  {i+1}. {corpus[i]}")
