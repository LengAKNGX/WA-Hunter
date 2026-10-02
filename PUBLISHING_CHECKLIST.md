# GitHub publishing checklist

## Repository settings

- Suggested repository name: `wa-hunter`
- Description: `Agentic differential testing and counterexample minimization for C++ array algorithms.`
- Visibility: Public
- Website: `https://lenga.com.cn`
- Issues: Enabled
- Suggested topics:
  - `differential-testing`
  - `competitive-programming`
  - `counterexample`
  - `delta-debugging`
  - `cpp`
  - `python`
  - `testing`
  - `algorithms`
- Default branch: `main`

Do not ask GitHub to create an extra README, `.gitignore`, or license when
creating the repository; this package already contains them.

## First release

1. Upload or push all packaged files, including `.github` and `.gitignore`.
2. Confirm the CI workflow passes.
3. Confirm **New issue** displays both structured forms.
4. Add the suggested topics and repository description.
5. Run the demo command from a fresh clone.
6. Create release `v0.1.0` with the title `WA Hunter MVP`.

## Public launch text

> WA Hunter is a small agentic differential-testing tool for C++ array
> algorithms. It generates structured tests, compares a candidate against a
> brute-force oracle, and minimizes the first mismatch. The repository also
> includes a reproducible buggy example and a ¥1 human-assisted beta service.

## Server follow-up

After the GitHub URL exists, add a small `/wa-hunter` landing page to the
existing domain. The first version should link to GitHub and the request form;
it should not accept code uploads or execute submissions.
