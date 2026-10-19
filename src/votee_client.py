import urllib.parse
import urllib.request
import urllib.error

import json
import time


BASE_URL = "https://wordle.votee.dev:8000"


class APIError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(f"[{status}] {message}")
        self.status = status
        self.message = message


class VoteeWordleClient:
    def __init__(self,
                base_url: str = BASE_URL,
                max_requests: int = 45,
                timeout: int = 10,
                delay: float = 0.25):
        self.base_url = base_url
        self.requests = 0
        self.max_requests = max_requests
        self.timeout = timeout
        self.delay = delay

    def _get(self, path: str, params: dict) -> list[dict]:
        """
        Shared behaviour for every request:
        budget check -> polite delay -> GET -> parse JSON or raise APIError.
        Returns e.g. [{"slot": 0, "guess": "c", "result": "absent"}, ...]
        """
        if self.requests >= self.max_requests:
            raise APIError(429, f"Request budget exhausted ({self.max_requests} requests)")

        if self.requests > 0 and self.delay > 0:
            time.sleep(self.delay)

        query = urllib.parse.urlencode(params)
        url = f"{self.base_url}{path}?{query}"
        self.requests += 1

        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as e:
            message = e.read().decode("utf-8", errors="replace") or e.reason
            raise APIError(e.code, message) from e
        except urllib.error.URLError as e:
            raise APIError(0, f"Network error: {e.reason}") from e
        except json.JSONDecodeError as e:
            raise APIError(0, f"Invalid JSON response: {e}") from e

    def daily(self, guess: str, size: int = 5) -> list[dict]:
        """Guess against today's puzzle."""
        return self._get("/daily", {"guess": guess, "size": size})

    def random(self, guess: str, size: int = 5, seed: int | None = None) -> list[dict]:
        """Guess against a random puzzle; same seed -> same word."""
        params = {"guess": guess, "size": size}
        if seed is not None:
            params["seed"] = seed
        return self._get("/random", params)

    def word(self, word: str, guess: str) -> list[dict]:
        """Guess against a chosen word."""
        return self._get(f"/word/{urllib.parse.quote(word)}", {"guess": guess})
