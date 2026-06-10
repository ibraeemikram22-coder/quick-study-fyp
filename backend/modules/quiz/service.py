def generate_quiz(file, count):
    content = file.read().decode("utf-8", errors="ignore")

    questions = []
    for i in range(min(count, 5)):
        questions.append({
            "question": f"Sample question {i+1}?",
            "options": ["A", "B", "C", "D"],
            "answer": "A"
        })

    return {
        "total": len(questions),
        "questions": questions
    }
