# Task definition
- Build a **14×14 adjacency matrix** of the molecular graph (atoms as nodes, bonds `aid1`/`aid2` as edges). Use files: _Conformer3D_COMPOUND_CID_4(1).json_, _Conformer3D_COMPOUND_CID_4(1).sdf_, _Conformer3D_COMPOUND_CID_4(1).asnt_.
- Compute **eigenvalues/eigenvectors** of the molecular adjacency matrix (graph spectrum — relates to molecular orbital theory.
- Build the **Laplacian** $L = D - A$ and find its null space (connected components).

## Laplacian meaning for this data
* It verifies the molecule is one connected object, not accidental fragments. In this code, the null-space dimension should match the number of connected components. For a valid single CID 4 molecule, that should be 1.
* It catches bad input or parsing mistakes. If a bond were missing in the JSON, the Laplacian analysis would show multiple components even if the file still “looked” structurally plausible.
* It summarizes which atoms are central and which are terminal. The degree matrix is basically “how many bonds does each atom have?” That is a fast structural summary before doing anything more advanced.
* It gives a topology fingerprint that is stable across conformers. The 3D coordinates can change from conformer to conformer, but if the bond graph is the same, the Laplacian should be the same. That makes it a good cross-check between structure files.
* It supports downstream graph algorithms. Shortest paths, spectral clustering ideas, graph ML features, and graph sanity checks all build naturally on the adjacency/Laplacian representation.

# Solution
## 1. Compute the degree vector

The degree of each atom is the number of bonds attached to it.

From the bond list:

- atom 1: degree 2
- atom 2: degree 3
- atom 3: degree 4
- atom 4: degree 4
- atom 5: degree 4
- atoms 6–14: degree 1

```json
{
	"degreeVector": [ 2, 3, 4, 4, 4, 1, 1, 1, 1, 1, 1, 1, 1, 1 ]
}
```

## 2. Build the degree matrix `D` (diagonal)

$$
D = \mathrm{diag}(2,3,4,4,4,1,1,1,1,1,1,1,1,1)
$$

$$
D = \begin{bmatrix}
2 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 \\
0 & 3 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 \\
0 & 0 & 4 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 \\
0 & 0 & 0 & 4 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 \\
0 & 0 & 0 & 0 & 4 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 \\
0 & 0 & 0 & 0 & 0 & 1 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 \\
0 & 0 & 0 & 0 & 0 & 0 & 1 & 0 & 0 & 0 & 0 & 0 & 0 & 0 \\
0 & 0 & 0 & 0 & 0 & 0 & 0 & 1 & 0 & 0 & 0 & 0 & 0 & 0 \\
0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 1 & 0 & 0 & 0 & 0 & 0 \\
0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 1 & 0 & 0 & 0 & 0 \\
0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 1 & 0 & 0 & 0 \\
0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 1 & 0 & 0 \\
0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 1 & 0 \\
0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 1
\end{bmatrix}
$$

---

## 3. Build the adjacency matrix `A`

Create a `14 × 14` matrix initialized to zero.

For each bond `(i, j)`:

- set `A[i-1][j-1] = 1`
- set `A[j-1][i-1] = 1`

The resulting adjacency matrix $A$ is:

```json
{
  "adjacencyMatrix": [
    [ 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1 ],
    [ 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0 ],
    [ 1, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0 ],
    [ 0, 1, 1, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0 ],
    [ 0, 0, 1, 0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0 ],
    [ 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 ],
    [ 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 ],
    [ 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 ],
    [ 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0 ],
    [ 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0 ],
    [ 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0 ],
    [ 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 ],
    [ 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 ],
    [ 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 ]
  ],
  "atomIds": [ 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14 ]
}
```
$$
A = \begin{bmatrix}
0 & 0 & 1 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 1 \\
0 & 0 & 0 & 1 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 1 & 1 & 0 \\
1 & 0 & 0 & 1 & 1 & 1 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 \\
0 & 1 & 1 & 0 & 0 & 0 & 1 & 1 & 0 & 0 & 0 & 0 & 0 & 0 \\
0 & 0 & 1 & 0 & 0 & 0 & 0 & 0 & 1 & 1 & 1 & 0 & 0 & 0 \\
0 & 0 & 1 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 \\
0 & 0 & 0 & 1 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 \\
0 & 0 & 0 & 1 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 \\
0 & 0 & 0 & 0 & 1 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 \\
0 & 0 & 0 & 0 & 1 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 \\
0 & 0 & 0 & 0 & 1 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 \\
0 & 1 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 \\
0 & 1 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 \\
1 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0
\end{bmatrix}
$$

---

## 4. Build the Laplacian matrix `L`

$L = D - A$, perform element-wise subtraction.
* If $i = j$ (Diagonal): $L_{i,i} = D_{i,i} - A_{i,i}$. Since $A_{i,i}$ is always $0$ (no self-loops). Diagonal entries = node degrees.
* If $i \neq j$ (Off-Diagonal): $L_{i,j} = 0 - A_{i,j}$. This means if there is an edge (`1`), i.e. a bond exists, it becomes `-1`. Otherwise `0`, i.e. no edge.

**Resulting Matrix:**
```json
{
	"laplacianMatrix": [
		[ 2.0, 0.0, -1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0 ],
		[ 0.0, 3.0, 0.0, -1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0, -1.0, 0.0 ],
		[ -1.0, 0.0, 4.0, -1.0, -1.0, -1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0 ],
		[ 0.0, -1.0, -1.0, 4.0, 0.0, 0.0, -1.0, -1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0 ],
		[ 0.0, 0.0, -1.0, 0.0, 4.0, 0.0, 0.0, 0.0, -1.0, -1.0, -1.0, 0.0, 0.0, 0.0 ],
		[ 0.0, 0.0, -1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0 ],
		[ 0.0, 0.0, 0.0, -1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0 ],
		[ 0.0, 0.0, 0.0, -1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0 ],
		[ 0.0, 0.0, 0.0, 0.0, -1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0 ],
		[ 0.0, 0.0, 0.0, 0.0, -1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0 ],
		[ 0.0, 0.0, 0.0, 0.0, -1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0 ],
		[ 0.0, -1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0 ],
		[ 0.0, -1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0 ],
		[ -1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0 ]
	]
}
```

$$
L = \begin{bmatrix}
2 & 0 & -1 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & -1 \\
0 & 3 & 0 & -1 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & -1 & -1 & 0 \\
-1 & 0 & 4 & -1 & -1 & -1 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 \\
0 & -1 & -1 & 4 & 0 & 0 & -1 & -1 & 0 & 0 & 0 & 0 & 0 & 0 \\
0 & 0 & -1 & 0 & 4 & 0 & 0 & 0 & -1 & -1 & -1 & 0 & 0 & 0 \\
0 & 0 & -1 & 0 & 0 & 1 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 \\
0 & 0 & 0 & -1 & 0 & 0 & 1 & 0 & 0 & 0 & 0 & 0 & 0 & 0 \\
0 & 0 & 0 & -1 & 0 & 0 & 0 & 1 & 0 & 0 & 0 & 0 & 0 & 0 \\
0 & 0 & 0 & 0 & -1 & 0 & 0 & 0 & 1 & 0 & 0 & 0 & 0 & 0 \\
0 & 0 & 0 & 0 & -1 & 0 & 0 & 0 & 0 & 1 & 0 & 0 & 0 & 0 \\
0 & 0 & 0 & 0 & -1 & 0 & 0 & 0 & 0 & 0 & 1 & 0 & 0 & 0 \\
0 & -1 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 1 & 0 & 0 \\
0 & -1 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 1 & 0 \\
-1 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 0 & 1
\end{bmatrix}
$$

---

## 5. Step-by-Step Subtraction

_Row 1_:
$$[2-0, 0-0, 0-1, 0-0, 0-0, 0-0, 0-0, 0-0, 0-0, 0-0, 0-0, 0-0, 0-0, 0-1] = [2, 0, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, -1]$$
_Row 2_:
$$[0-0, 3-0, 0-0, 0-1, 0-0 0-0, 0-0, 0-0, 0-0, 0-0, 0-0, 0-1, 0-1, 0-0] = [0, 3, 0, -1, 0, 0, 0, 0, 0, 0, 0, -1, -1, 0]$$
_Row 3_:
$$[0-1, 0-0, 4-0, 0-1, 0-1, 0-1, 0-0, 0-0, 0-0, 0-0, 0-0, 0-0, 0-0, 0-0] = [-1, 0, 4, -1, -1, -1, 0, 0, 0, 0, 0, 0, 0, 0]$$
_Row 4_:
$$[0-0, 0-1, 0-1, 4-0, 0-0, 0-0, 0-1 0-1, 0-0, 0-0, 0-0, 0-0, 0-0, 0-0] = [0, -1, -1, 4, 0, 0, -1 -1, 0, 0, 0, 0, 0, 0]$$
_Row 5_:
$$[0-0, 0-0, 0-1, 0-0, 4-0, 0-0, 0-0, 0-0, 0-1, 0-1, 0-1, 0-0, 0-0, 0-0] = [0, 0, -1, 0, 4, 0, 0, 0, -1, -1, -1, 0, 0, 0]$$
_Row 6_:
$$[0-0, 0-0, 0-1, 0-0, 0-0, 1-0, 0-0, 0-0, 0-0, 0-0, 0-0, 0-0, 0-0, 0-0] = [0, 0, -1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0]$$
_Row 7_:
$$[0-0, 0-0, 0-0, 0-1, 0-0, 0-0, 1-0, 0-0, 0-0, 0-0, 0-0, 0-0, 0-0, 0-0] = [0, 0, 0, -1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0]$$
_Row 8_:
$$[0-0, 0-0, 0-0, 0-1, 0-0, 0-0, 0-0, 1-0, 0-0, 0-0, 0-0, 0-0, 0-0, 0-0] = [0, 0, 0, -1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0]$$
_Row 9_:
$$[0-0, 0-0, 0-0, 0-0, 0-1, 0-0, 0-0, 0-0, 1-0, 0-0, 0-0, 0-0, 0-0, 0-0] = [0, 0, 0, 0, -1, 0, 0, 0, 1, 0, 0, 0, 0, 0]$$
_Row 10_:
$$[0-0, 0-0, 0-0, 0-0, 0-1, 0-0, 0-0, 0-0, 0-0, 1-0, 0-0, 0-0, 0-0, 0-0] = [0, 0, 0, 0, -1, 0, 0, 0, 0, 1, 0, 0, 0, 0]$$
_Row 11_:
$$[0-0, 0-0, 0-0, 0-0, 0-1, 0-0, 0-0, 0-0, 0-0, 0-0, 1-0, 0-0, 0-0, 0-0] = [0, 0, 0, 0, -1, 0, 0, 0, 0, 0, 1, 0, 0, 0]$$
_Row 12_:
$$[0-0, 0-1, 0-0, 0-0, 0-0, 0-0, 0-0, 0-0, 0-0, 0-0, 0-0, 1-0, 0-0, 0-0] = [0, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0]$$
_Row 13_:
$$[0-0, 0-1, 0-0, 0-0, 0-0, 0-0, 0-0, 0-0, 0-0, 0-0, 0-0, 0-0, 1-0, 0-0] = [0, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0]$$
_Row 14_:
$$[0-1, 0-0, 0-0, 0-0, 0-0, 0-0, 0-0, 0-0, 0-0, 0-0, 0-0, 0-0, 0-0, 1-0] = [-1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]$$
