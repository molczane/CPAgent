import sys


def main() -> None:
    lines = sys.stdin.read().splitlines()
    if not lines:
        return

    h, w = map(int, lines[0].split())
    grid = lines[1 : 1 + h]

    start = target = None
    for r in range(h):
        for c in range(w):
            if grid[r][c] == "S":
                start = (r, c)
            elif grid[r][c] == "T":
                target = (r, c)

    if start is None or target is None:
        print(-1)
        return

    sr, sc = start
    tr, tc = target
    print(abs(sr - tr) + abs(sc - tc))


if __name__ == "__main__":
    main()
