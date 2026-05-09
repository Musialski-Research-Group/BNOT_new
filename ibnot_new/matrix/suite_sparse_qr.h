#ifndef _SUITESPARSEQR_WRAPPER_H
#define _SUITESPARSEQR_WRAPPER_H 1

// STL
#include <cmath>
#include <vector>

// Eigen
#include <Eigen/SparseCore>
#include <Eigen/SparseQR>
#include <Eigen/OrderingMethods>

// local
#include "sparse_matrix.h"

class SparseQRFactorizer {
private:
    typedef Eigen::SparseMatrix<double, Eigen::ColMajor, int> EigenSparseMatrix;
    typedef Eigen::Triplet<double, int> EigenTriplet;
    typedef Eigen::SparseQR<EigenSparseMatrix, Eigen::COLAMDOrdering<int> > EigenSolver;

    EigenSparseMatrix m_matrix;
    EigenSolver m_solver;
    bool m_ready;
    
public:
    SparseQRFactorizer()
    {
        m_ready = false;
    }
    
    bool factorize(const SparseMatrix& A)
    {
        m_matrix = convert_to_eigen_sparse(A);
        m_solver.compute(m_matrix);
        m_ready = (m_solver.info() == Eigen::Success);
        return m_ready;
    }
    
    bool solve(const std::vector<double>& rhs, std::vector<double>& x)
    {
        if (!m_ready) return false;

        Eigen::VectorXd b = Eigen::VectorXd::Zero(rhs.size());
        for (unsigned i = 0; i < rhs.size(); ++i) b[static_cast<int>(i)] = rhs[i];

        Eigen::VectorXd solution = m_solver.solve(b);
        if (m_solver.info() != Eigen::Success) return false;

        x.resize(solution.size());
        for (int i = 0; i < solution.size(); ++i)
        {
            if (!std::isfinite(solution[i])) return false;
            x[static_cast<unsigned>(i)] = solution[i];
        }
        return true;
    }
    
private:
    EigenSparseMatrix convert_to_eigen_sparse(const SparseMatrix& A) const
    {
        std::vector<EigenTriplet> triplets;
        triplets.reserve(A.numNonZeros());

        for (unsigned i = 0; i < A.numRows(); ++i)
        {
            SparseArray row = A.getRow(i);
            for (unsigned j = 0; j < row.numNonZeros(); ++j)
            {
                triplets.push_back(EigenTriplet(static_cast<int>(i),
                                                static_cast<int>(row.readIndex(j)),
                                                row.readValue(j)));
            }
        }

        EigenSparseMatrix matrix(static_cast<int>(A.numRows()),
                                 static_cast<int>(A.numColumns()));
        matrix.setFromTriplets(triplets.begin(), triplets.end());
        matrix.makeCompressed();
        return matrix;
    }
};

#endif
