# Club Fair Schedule

Your school is running a club fair. Each club wants to give a short presentation in the same auditorium.

For each presentation you know its start time and end time. You can attend two presentations back to back if the first one ends at the exact time the next one starts.

Find the maximum number of presentations you can attend.

## Input

The first line contains an integer `n`.

Each of the next `n` lines contains two integers `start` and `end`.

## Output

Print one integer: the maximum number of non-overlapping presentations.

## Constraints

- `1 <= n <= 200000`
- `0 <= start < end <= 10^9`

## Example

Input:

```text
4
1 10
2 3
3 4
4 5
```

Output:

```text
3
```
