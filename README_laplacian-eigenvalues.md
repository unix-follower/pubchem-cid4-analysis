# Task definition
Compute the eigenvalues of [Laplacian](./README_laplacian.md)
$$
\det(L - \lambda I) = 0
$$

## Eigenvalues meaning for this data
* **One zero eigenvalue** means the graph has **one connected component (molecule)**;
* more than one zero eigenvalue means the graph has split into pieces;
* the smallest nonzero eigenvalue is a rough measure of how easily the graph could be separated;
* the second-smallest eigenvalue
$$
\lambda_2 = 0.15009381179305936
$$

is the **algebraic connectivity** or **Fiedler value**

---

## Minimal Python code

````python
import numpy as np

n = 14
bonds = [
    (1, 3), (1, 14),
    (2, 4), (2, 12), (2, 13),
    (3, 4), (3, 5), (3, 6),
    (4, 7), (4, 8),
    (5, 9), (5, 10), (5, 11),
]

A = np.zeros((n, n), dtype=float)
for i, j in bonds:
    A[i - 1, j - 1] = 1.0
    A[j - 1, i - 1] = 1.0

D = np.diag(A.sum(axis=1))
L = D - A

eigenvalues = np.linalg.eigvalsh(L)

print("Adjacency matrix A:\n", A)
print("Degree vector:", A.sum(axis=1).tolist())
print("Laplacian L:\n", L)
print("Laplacian eigenvalues:\n", eigenvalues.tolist())
````

---

# Solution
```bash
laplacian_analysis_file_path="$DATA_DIR/out/Conformer3D_COMPOUND_CID_4(1).armadillo.laplacian_analysis.json"
```

1. Build the Laplacian `L`.
2. Take the normalized all-ones vector:

$$
v = \frac{1}{\sqrt{14}}(1,1,\dots,1)^T
$$

3. Multiply `L v`.
4. Every row cancels as `degree × c - sum of neighbor c's = 0`.
5. The exact eigenvalue is:
$$
\lambda_1 = 0
$$

For a connected graph, the Laplacian always has the eigenpair:

$$
\lambda = 0, \quad v = \mathbf{1}
$$

or, in normalized form,

$$
v = \frac{1}{\sqrt{14}}
\begin{bmatrix}
1\\1\\1\\1\\1\\1\\1\\1\\1\\1\\1\\1\\1\\1
\end{bmatrix}
=
\begin{bmatrix}
0.2672612419124244\\
0.2672612419124244\\
\vdots\\
0.2672612419124244
\end{bmatrix}
$$

That _almost_ matches the eigenvector stored in `nullSpace`.

---

## 1. Use the normalized null-space vector

Since there are 14 atoms,

$$
\sqrt{14} \approx 3.7416573867739413
$$

so

$$
\frac{1}{\sqrt{14}} \approx 0.2672612419124244
$$

Thus the candidate eigenvector is

$$
v \approx
\begin{bmatrix}
0.2672612419124244\\
0.2672612419124244\\
0.2672612419124244\\
0.2672612419124244\\
0.2672612419124244\\
0.2672612419124244\\
0.2672612419124244\\
0.2672612419124244\\
0.2672612419124244\\
0.2672612419124244\\
0.2672612419124244\\
0.2672612419124244\\
0.2672612419124244\\
0.2672612419124244
\end{bmatrix}
$$
In the perfect world, the constant vector `v` has `c = 0.2672612419124244`.
In reality, `v` is _almost_ the all-ones vector, but with tiny residuals.
```json
{
  "laplacianEigenvectors": [
    [0.26726124191242184],
    [0.26726124191242523],
    [0.2672612419124238],
    [0.2672612419124248],
    [0.26726124191242545],
    [0.2672612419124237],
    [0.26726124191242473],
    [0.26726124191242484],
    [0.26726124191242573],
    [0.26726124191242584],
    [0.26726124191242584],
    [0.2672612419124253],
    [0.2672612419124253],
    [0.2672612419124206]
  ]
}
```
## 2. Apply the Laplacian row by row

For Laplacian matrices,

$$
(Lv)_i = d_i v_i - \sum_{j \sim i} v_j
$$

Because every entry of `v` is the same constant $$c = 1/\sqrt{14}$$, each row becomes:

$$
(Lv)_i = d_i c - d_i c = 0
$$

## 3. Resulting Laplacian eigenvalues

For this molecule, the eigenvalues are:

```json
{
    "laplacianEigenvalues": [
        -3.686287386450727e-18,
        0.15009381179305936,
        0.30223197908387894,
        0.49392902949411727,
        0.7474958209410854,
        0.9999999999999994,
        0.9999999999999999,
        1.0,
        1.0000000000000002,
        2.269015806193034,
        3.1650303318023756,
        3.9072445381083005,
        4.964868133902638,
        6.0000905486815075
    ]
}
```

# Step-by-step calculations
## λ₁
$$\lambda_1 = -3.686287386450727e^{-18} \approx 0$$
The first value `-3.686287386450727e-18` is essentially `0`. It appears slightly negative only because of floating-point error.

$$
-3.686287386450727 \times 10^{-18}
$$

This is:

$$
-0.000000000000000003686287386450727
$$

```json
"tolerance": 1e-10
```

Compare magnitudes:

$$
|-3.686287386450727 \times 10^{-18}| = 3.686287386450727 \times 10^{-18}
$$

and

$$
1 \times 10^{-10}
$$

Since

$$
3.686287386450727 \times 10^{-18} \ll 10^{-10}
$$

it is classified as a **zero eigenvalue**.

### Row 1
```bash
# get row 1
jq -r '.laplacianMatrix[0]' --compact-output $laplacian_analysis_file_path

# get row 1 column 1 = 0.26726124191242184
jq -r '.laplacianEigenvectors[0][0]' $laplacian_analysis_file_path
```

Atom 1 has degree 2 and neighbors 3 and 14:
$$
(Lv)_1 = 2c - (c + c) = 2c - 2c = 0
\\
(Lv)_1 = 2*c + 0*c + (-1)*c + 0*c + 0*c \\
    + 0*c + 0*c + 0*c + 0*c + 0*c \\
    + 0*c + 0*c + 0*c + (-1)*c = 0
$$

### Row 2
```bash
# get row 2
jq -r '.laplacianMatrix[1]' --compact-output $laplacian_analysis_file_path

# get row 2 column 1 = 0.26726124191242523
jq -r '.laplacianEigenvectors[1][0]' $laplacian_analysis_file_path
```

Atom 2 has degree 3 and neighbors 4, 12, 13:
$$
(Lv)_2 = 3c - (c + c + c) = 3c - 3c = 0
\\
(Lv)_2 = 0*c + 3*c + 0*c + (-1)*c + 0*c \\
    + 0*c + 0*c + 0*c + 0*c + 0*c \\
    + 0*c + (-1)*c + (-1)*c + 0*c = 0
$$

### Row 3
```bash
# get row 3
jq -r '.laplacianMatrix[2]' --compact-output $laplacian_analysis_file_path

# get row 3 column 1 = 0.2672612419124238
jq -r '.laplacianEigenvectors[2][0]' $laplacian_analysis_file_path
```

Atom 3 has degree 4 and neighbors 1, 4, 5, 6:
$$
(Lv)_3 = 4c - (c + c + c + c) = 4c - 4c = 0
\\
(Lv)_3 = (-1)*c + 0*c + 4*c + (-1)*c + (-1)*c \\
    + (-1)*c + 0*c + 0*c + 0*c + 0*c \\
    + 0*c + 0*c + 0*c + 0*c = 0
$$

### Row 4
```bash
# get row 4
jq -r '.laplacianMatrix[3]' --compact-output $laplacian_analysis_file_path

# get row 4 column 1 = 0.2672612419124248
jq -r '.laplacianEigenvectors[3][0]' $laplacian_analysis_file_path
```

Atom 4 has degree 4 and neighbors 2, 3, 7, 8:
$$
(Lv)_4 = 4c - (c + c + c + c) = 0
\\
(Lv)_4 = 0*c + (-1)*c + (-1)*c + 4*c + 0*c \\
    + 0*c + (-1)*c + (-1)*c + 0*c + 0*c \\
    + 0*c + 0*c + 0*c + 0*c = 0
$$

### Row 5
```bash
# get row 5
jq -r '.laplacianMatrix[4]' --compact-output $laplacian_analysis_file_path

# get row 5 column 1 = 0.26726124191242545
jq -r '.laplacianEigenvectors[4][0]' $laplacian_analysis_file_path
```

Atom 5 has degree 4 and neighbors 3, 9, 10, 11:
$$
(Lv)_5 = 4c - (c + c + c + c) = 0
\\
(Lv)_5 = 0*c + 0*c + (-1)*c + 0*c + 4*c \\
    + 0*c + 0*c + 0*c + (-1)*c + (-1)*c \\
    + (-1)*c + 0*c + 0*c + 0*c = 0
$$

### Rows 6 to 14
Each of these is a leaf with degree 1, so each row is:

$$
(Lv)_i = 1\cdot c - c = 0
$$

### Row 6: neighbor 3
```bash
# get row 6
jq -r '.laplacianMatrix[5]' --compact-output $laplacian_analysis_file_path

# get row 6 column 1 = 0.2672612419124237
jq -r '.laplacianEigenvectors[5][0]' $laplacian_analysis_file_path
```

$$
(Lv)_6 = 0*c + 0*c + (-1)*c + 0*c + 0*c \\
    + 1*c + 0*c + 0*c + 0*c + 0*c \\
    + 0*c + 0*c + 0*c + 0*c = 0
$$

### Row 7: neighbor 4
```bash
# get row 7
jq -r '.laplacianMatrix[6]' --compact-output $laplacian_analysis_file_path

# get row 7 column 1 = 0.26726124191242473
jq -r '.laplacianEigenvectors[6][0]' $laplacian_analysis_file_path
```

$$
(Lv)_7 = 0*c + 0*c + 0*c + (-1)*c + 0*c \\
    + 0*c + 1*c + 0*c + 0*c + 0*c \\
    + 0*c + 0*c + 0*c + 0*c = 0
$$
### Row 8: neighbor 4
```bash
# get row 8
jq -r '.laplacianMatrix[7]' --compact-output $laplacian_analysis_file_path

# get row 8 column 1 = 0.26726124191242484
jq -r '.laplacianEigenvectors[7][0]' $laplacian_analysis_file_path
```

$$
(Lv)_8 = 0*c + 0*c + 0*c + (-1)*c + 0*c \\
    + 0*c + 0*c + 1*c + 0*c + 0*c \\
    + 0*c + 0*c + 0*c + 0*c = 0
$$
### Row 9: neighbor 5
```bash
# get row 9
jq -r '.laplacianMatrix[8]' --compact-output $laplacian_analysis_file_path

# get row 9 column 1 = 0.26726124191242573
jq -r '.laplacianEigenvectors[8][0]' $laplacian_analysis_file_path
```

$$
(Lv)_9 = 0*c + 0*c + 0*c + 0*c + (-1)*c \\
    + 0*c + 0*c + 0*c + 1*c + 0*c \\
    + 0*c + 0*c + 0*c + 0*c = 0
$$
### Row 10: neighbor 5
```bash
# get row 10
jq -r '.laplacianMatrix[9]' --compact-output $laplacian_analysis_file_path

# get row 10 column 1 = 0.26726124191242584
jq -r '.laplacianEigenvectors[9][0]' $laplacian_analysis_file_path
```

$$
(Lv)_{10} = 0*c + 0*c + 0*c + 0*c + (-1)*c \\
    + 0*c + 0*c + 0*c + 1*c + 0*c \\
    + 0*c + 0*c + 0*c + 0*c = 0
$$
### Row 11: neighbor 5
```bash
# get row 11
jq -r '.laplacianMatrix[10]' --compact-output $laplacian_analysis_file_path

# get row 11 column 1 = 0.26726124191242584
jq -r '.laplacianEigenvectors[10][0]' $laplacian_analysis_file_path
```

$$
(Lv)_{11} = 0*c + 0*c + 0*c + 0*c + (-1)*c \\
    + 0*c + 0*c + 0*c + 0*c + 0*c \\
    + 1*c + 0*c + 0*c + 0*c = 0
$$
### Row 12: neighbor 2
```bash
# get row 12
jq -r '.laplacianMatrix[11]' --compact-output $laplacian_analysis_file_path

# get row 12 column 1 = 0.2672612419124253
jq -r '.laplacianEigenvectors[11][0]' $laplacian_analysis_file_path
```

$$
(Lv)_{12} = 0*c + (-1)*c + 0*c + 0*c + 0*c \\
    + 0*c + 0*c + 0*c + 0*c + 0*c \\
    + 0*c + 1*c + 0*c + 0*c = 0
$$
### Row 13: neighbor 2
```bash
# get row 13
jq -r '.laplacianMatrix[12]' --compact-output $laplacian_analysis_file_path

# get row 13 column 1 = 0.2672612419124253
jq -r '.laplacianEigenvectors[12][0]' $laplacian_analysis_file_path
```

$$
(Lv)_{13} = 0*c + (-1)*c + 0*c + 0*c + 0*c \\
    + 0*c + 0*c + 0*c + 0*c + 0*c \\
    + 0*c + 0*c + 1*c + 0*c = 0
$$
### Row 14: neighbor 1
```bash
# get row 14
jq -r '.laplacianMatrix[13]' --compact-output $laplacian_analysis_file_path

# get row 14 column 1 = 0.2672612419124206
jq -r '.laplacianEigenvectors[13][0]' $laplacian_analysis_file_path
```

$$
(Lv)_{14} = (-1)*c + 0*c + 0*c + 0*c + 0*c \\
    + 0*c + 0*c + 0*c + 0*c + 0*c \\
    + 0*c + 0*c + 0*c + 1*c = 0
$$

## λ₂
This value is the **second-smallest Laplacian eigenvalue**.  
Its eigenvector is the **second column** of `laplacianEigenvectors`:

$$
v =
\begin{bmatrix}
0.1306101596249139 \\
-0.3427432643342508 \\
0.08794057048176407 \\
-0.17024239471670571 \\
0.274724267144246 \\
0.1034709144397379 \\
-0.20030727753126365 \\
-0.20030727753126348 \\
0.32324069521582843 \\
0.32324069521582854 \\
0.32324069521582843 \\
-0.40327187763786143 \\
-0.40327187763786143 \\
0.15367597205106096
\end{bmatrix}
$$

## Row 1
```bash
# get row 1
jq -r '.laplacianMatrix[0]' --compact-output $laplacian_analysis_file_path

# get row 1 column 2 = 0.1306101596249139
jq -r '.laplacianEigenvectors[0][1]' $laplacian_analysis_file_path
# get row 3 column 2 = 0.08794057048176407
jq -r '.laplacianEigenvectors[2][1]' $laplacian_analysis_file_path
# get row 14 column 2 = 0.15367597205106096
jq -r '.laplacianEigenvectors[13][1]' $laplacian_analysis_file_path
```
Atom 1 has degree 2 and neighbors 3 and 14:

$$
(Lv)_1 = 2v_1 - v_3 - v_{14}
$$

$$
= 2(0.1306101596249139) + (-1)0.08794057048176407 + (-1)0.15367597205106096
$$

$$
= 0.019603776717002764
$$

$$
\lambda_1 = \frac{(Lv)_1}{v_1}
= \frac{0.019603776717002764}{0.1306101596249139}
= 0.15009381179305936
$$

## Row 2
```bash
# get row 1
jq -r '.laplacianMatrix[1]' --compact-output $laplacian_analysis_file_path

# get row 2 column 2 = -0.3427432643342508 
jq -r '.laplacianEigenvectors[1][1]' $laplacian_analysis_file_path
# get row 3 column 2 = -0.17024239471670571
jq -r '.laplacianEigenvectors[3][1]' $laplacian_analysis_file_path
# get row 12 column 2 = -0.40327187763786143
jq -r '.laplacianEigenvectors[11][1]' $laplacian_analysis_file_path
# get row 13 column 2 = -0.40327187763786143
jq -r '.laplacianEigenvectors[12][1]' $laplacian_analysis_file_path
```
Atom 2 has degree 3 and neighbors 4, 12, 13.

$$
(Lv)_2 = 3v_2 - v_4 - v_{12} - v_{13}
$$

$$
= 3*(-0.3427432643342508)+(-1)*(-0.17024239471670571)+(-1)*(-0.40327187763786143)+(-1)*(-0.40327187763786143)
$$

$$
= -0.0514436430103238
$$

$$
\lambda_2 = \frac{(Lv)_2}{v_2} = \frac{-0.0514436430103238}{-0.3427432643342508}
= 0.15009381179305936
$$
