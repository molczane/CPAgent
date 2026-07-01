# Contest Hall Maze

During a programming contest, a small delivery robot has to carry printed clarifications from the judges' table to a contestant.

The contest hall is drawn as a grid:

- `S` is the robot's starting cell.
- `T` is the target contestant.
- `.` is an open cell.
- `#` is a blocked cell full of chairs and backpacks.

The robot can move up, down, left, or right. Find the minimum number of moves needed to reach `T`, or print `-1` if it is impossible.

This is a shortest path problem on an unweighted grid.

## Input

The first line contains two integers `h` and `w`.

Each of the next `h` lines contains `w` characters.

## Output

Print one integer: the minimum number of moves from `S` to `T`, or `-1`.

## Constraints

- `1 <= h, w <= 1000`
- The grid contains exactly one `S` and exactly one `T`.
- The total number of cells is at most `200000`.

## Example

Input:

```text
3 5
S.#..
..#.T
.....
```

Output:

```text
6
```
