# repository-template
A repository template for repository creation at Scale AI.

## Usage
### Automatic
Request a new repository from the slackbot `Onyx` using `/onyx` and input the appropriate information such as desired language(s).

Optionally scaffolds `CODEOWNERS` and `entity.datadog.yaml` when a GitHub owning team is selected. Workflow inputs `github_owner` and `description` are optional and skipped when unset.

### Manual
Requires repository creation permissions and an appropriately-permissioned REPO_SETUP_TOKEN

1. Create a new repository using this template
2. Add a secret `REPO_SETUP_TOKEN` to the new repository
3. Run the GitHub workflow `repository-setup`, inputting parameters as desired.
4. Allow the workflow to run and set up language-specific files and settings.
