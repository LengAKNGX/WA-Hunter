#include <iostream>
#include <vector>
using namespace std;

// Intentionally wrong: adjacent increases do not model whole-segment maxima.
int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    cin >> n;
    vector<int> a(n);
    for (int &x : a) cin >> x;

    int days = 1;
    for (int i = 1; i < n; ++i) {
        if (a[i] > a[i - 1]) ++days;
    }
    cout << days << '\n';
}
