from app.auth.pkce import generate_code_challenge, generate_code_verifier


def test_pkce_generation():
    verifier = generate_code_verifier()
    assert 43 <= len(verifier) <= 128
    challenge = generate_code_challenge(verifier)
    assert challenge
    assert "=" not in challenge

