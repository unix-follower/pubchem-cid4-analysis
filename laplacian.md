# Task definition
- Build a **14×14 adjacency matrix** of the molecular graph (atoms as nodes, bonds `aid1`/`aid2` as edges). Use files: Conformer3D_COMPOUND_CID_4(1).json, Conformer3D_COMPOUND_CID_4(1).sdf, Conformer3D_COMPOUND_CID_4(1).asnt.
- Compute **eigenvalues/eigenvectors** of the molecular adjacency matrix (graph spectrum — relates to molecular orbital theory.
- Build the **Laplacian** $L = D - A$ and find its null space (connected components).

## Eigenvalues meaning for this data
* one zero eigenvalue means one connected molecule;
* more than one zero eigenvalue means the graph has split into pieces;
* the smallest nonzero eigenvalue is a rough measure of how easily the graph could be separated.

## Laplacian meaning for this data
* It verifies the molecule is one connected object, not accidental fragments. In this code, the null-space dimension should match the number of connected components. For a valid single CID 4 molecule, that should be 1.
* It catches bad input or parsing mistakes. If a bond were missing in the JSON, the Laplacian analysis would show multiple components even if the file still “looked” structurally plausible.
* It summarizes which atoms are central and which are terminal. The degree matrix is basically “how many bonds does each atom have?” That is a fast structural summary before doing anything more advanced.
* It gives a topology fingerprint that is stable across conformers. The 3D coordinates can change from conformer to conformer, but if the bond graph is the same, the Laplacian should be the same. That makes it a good cross-check between structure files.
* It supports downstream graph algorithms. Shortest paths, spectral clustering ideas, graph ML features, and graph sanity checks all build naturally on the adjacency/Laplacian representation.

# Solution
To compute the Laplacian matrix $L = D - A$, perform element-wise subtraction.
* If $i = j$ (Diagonal): $L_{i,i} = D_{i,i} - A_{i,i}$. Since $A_{i,i}$ is always $0$ (no self-loops), the diagonal of $L$ is just the degree of that node.
* If $i \neq j$ (Off-Diagonal): $L_{i,j} = 0 - A_{i,j}$. This means if there is an edge ($1$), it becomes $-1$. If there is no edge ($0$), it stays $0$.
---
**1. The Degree Matrix ($D$)**

The degree matrix is a diagonal matrix where $D_{ii}$ is the degree of node $i$. Based on the degree vector:
```json
{
	"degreeVector": [ 2.0, 3.0, 4.0, 4.0, 4.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0 ]
}
```
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
**2. The Adjacency Matrix ($A$)**

This represents the connections between nodes.
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
**3. Step-by-Step Subtraction ($L = D - A$)**

$L_{ij} = D_{ij} - A_{ij}$. Since $D$ is diagonal, the diagonal of $L$ is simply the degree, and the off-diagonal entries are $-1$ if an edge exists and $0$ otherwise.

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
Resulting Matrix:
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
