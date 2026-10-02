#include <algorithm>
#include <iostream>
#include <vector>
using namespace std;

// Codeforces: Harder Horizons
// O(n) greedy solution.
//
// Close every day at the earliest position where its maximum is strictly
// greater than the previous day's maximum. This makes the current maximum as
// small as possible and leaves the longest possible suffix for later days.
int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    cin >> n;
    vector<int> difficulty(n);
    for (int &x : difficulty) cin >> x;

    int days = 1;
    int previous_max = difficulty[0];
    int current_max = 0;

    for (int i = 1; i < n; ++i) {
        current_max = max(current_max, difficulty[i]);
        if (current_max > previous_max) {
            ++days;
            previous_max = current_max;
            current_max = 0;
        }
    }

    cout << days << '\n';
    return 0;
}
