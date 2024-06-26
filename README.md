# Ansible Collection - karcadia.harness

Harness is a Software Delivery Platform specializing in CI/CD. Use this collection to manage your Harness Account and all the objects within.
Harness objects sit in a hierarchy:
- Account
- Org
- Project

Normal Objects:
- Delegates
- Connectors
- Secrets
- Roles

All remaining objects then live in one or more of their hierarchical parents. So a normal object like a Secret can be scoped into the Account, the Org, or the Project. All objects, including Orgs, must live in an Account. All projects must live in an Org. Normal objects can live in an Account, an Org, or a Project.

This is reflected in the code, where the module code for most objects is identical except for the module.object_type line and the documentation.
The primary exceptions to this are the Org and Project modules, which differ a bit more due to their hierarchical nature.

Requirements:
- Python 3.6+
- Python Requests Library