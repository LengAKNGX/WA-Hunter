#include <algorithm>
#include <iostream>
#include <map>
#include <vector>
using namespace std;

// Independent small-input oracle.
// dp[r][m] = maximum number of days for prefix [0..r] when the final day's
// maximum is m. Every possible last segment [left..right] is considered.
// Complexity is O(n^3) in the worst case, suitable for WA Hunter's small tests.
int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    cin >> n;
    vector<int> difficulty(n);
    for (int &x : difficulty) cin >> x;

    vector<map<int, int>> dp(n);
    for (int right = 0; right < n; ++right) {
        int segment_max = 0;
        for (int left = right; left >= 0; --left) {
            segment_max = max(segment_max, difficulty[left]);
            if (left == 0) {
                dp[right][segment_max] = max(dp[right][segment_max], 1);
                continue;
            }

            for (const auto &[previous_max, previous_days] : dp[left - 1]) {
                if (previous_max < segment_max) {
                    dp[right][segment_max] =
                        max(dp[right][segment_max], previous_days + 1);
                }
            }
        }
    }

    int answer = 1;
    for (const auto &[last_max, days] : dp[n - 1]) {
        (void)last_max;
        answer = max(answer, days);
    }
    cout << answer << '\n';
    return 0;
}
