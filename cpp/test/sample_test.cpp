#include <gtest/gtest.h>

TEST(SampleTest, BasicAssertion)
{
    EXPECT_EQ(1 + 1, 2);
    EXPECT_TRUE(true);
}

TEST(SampleTest, StringComparison)
{
    std::string expected = "Hello";
    std::string actual = "Hello";
    EXPECT_EQ(expected, actual);
}

TEST(SampleTest, FloatingPointComparison)
{
    double a = 0.1 + 0.2;
    double b = 0.3;
    EXPECT_NEAR(a, b, 1e-10);
}
