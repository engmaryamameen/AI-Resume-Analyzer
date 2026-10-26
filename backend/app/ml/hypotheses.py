"""The statements a requirement is verified as. Training data and inference both build them here, so the
verifier is always given the same wording it was trained on."""


def skill_hypothesis(name: str) -> str:
    return f"The candidate has hands-on experience with {name}."


def soft_skill_hypothesis(name: str) -> str:
    return f"The candidate has demonstrated {name}."


def certification_hypothesis(text: str) -> str:
    return f"The candidate holds the certification: {text}"


def experience_hypothesis(subject: str) -> str:
    return f"The candidate has professional experience in {subject}."


def responsibility_hypothesis(text: str) -> str:
    return f"The candidate has experience with the following: {text}"
