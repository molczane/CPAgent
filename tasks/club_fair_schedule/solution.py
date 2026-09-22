import sys


def main() -> None:
    data = sys.stdin.buffer.read().split()
    if not data:
        return

    n = int(data[0])
    intervals = []
    index = 1
    for _ in range(n):
        start = int(data[index])
        end = int(data[index + 1])
        intervals.append((start, end))
        index += 2

    # Greedy: sort by start time and pick the next non-overlapping presentation
    intervals.sort(key=lambda x: x[0])

    answer = 0
    current_end = -1
    for start, end in intervals:
        if start >= current_end:
            answer += 1
            current_end = end

    sys.stdout.write(str(answer) + "\n")


if __name__ == "__main__":
    main()
