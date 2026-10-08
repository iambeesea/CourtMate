"""Turn a submitted result into a stored score, using the sport's own scoring rules."""

from .. import schemas

MAX_POINTS = 999


class ScoreError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _whole(value: int, ceiling: int = MAX_POINTS) -> int:
    if value < 0 or value > ceiling:
        raise ScoreError(f"Scores must be between 0 and {ceiling}.")
    return value


def score_match(config: dict, result: schemas.MatchResultIn) -> tuple[dict, int | None, bool]:
    """Validate `result` against a sport's scoring_config. Returns (score, winner_side, is_draw)."""
    kind = config.get("kind")
    allow_draw = bool(config.get("allowDraw"))

    if kind == "games":
        if not result.games:
            raise ScoreError(f"Enter the score of each {(config.get('gameLabel') or 'game').rstrip('s').lower()}.")
        best_of = config.get("bestOf")
        if best_of and len(result.games) > best_of:
            raise ScoreError(f"This sport is played best of {best_of}.")
        games = [[_whole(first), _whole(second)] for first, second in result.games]
        if any(first == second for first, second in games):
            raise ScoreError("A game cannot end level.")
        won = [sum(first > second for first, second in games), sum(second > first for first, second in games)]
        score = {"games": games, "totals": won}
    elif kind == "total":
        if result.totals is None:
            raise ScoreError(f"Enter each side's {config.get('unit') or 'score'}.")
        won = [_whole(result.totals[0], 9999), _whole(result.totals[1], 9999)]
        score = {"totals": won}
    elif kind == "result":
        if result.draw:
            won = [0, 0]
        elif result.winner in (1, 2):
            won = [1, 0] if result.winner == 1 else [0, 1]
        else:
            raise ScoreError("Say who won, or record a draw.")
        score = {}
    else:
        raise ScoreError("This sport does not record head-to-head results.")

    if won[0] == won[1]:
        if not allow_draw:
            raise ScoreError("The result is level. This sport needs a winner.")
        return score, None, True
    return score, 1 if won[0] > won[1] else 2, False


def player_stat_lines(config: dict, submitted: dict[str, dict[str, int]], player_ids: set[str]) -> dict[str, dict[str, int]]:
    """Keep only stat lines for players in the match and fields the sport defines."""
    allowed = {field["key"] for field in config.get("playerFields", [])}
    lines: dict[str, dict[str, int]] = {}
    for user_id, stats in submitted.items():
        if user_id not in player_ids:
            raise ScoreError("Statistics were submitted for someone who did not play in this match.")
        if unknown := sorted(set(stats) - allowed):
            raise ScoreError(f"This sport does not track: {', '.join(unknown)}.")
        lines[user_id] = {key: _whole(value) for key, value in stats.items()}
    return lines
