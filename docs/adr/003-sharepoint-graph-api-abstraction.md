# ADR 003: DocumentationProvider Abstraction (Microsoft Graph & Local Mirror)

## Status
Accepted

## Context
The resume bullet asserts: *"documenting the outcomes in SharePoint."* While enterprise deployments connect to Microsoft 365 SharePoint Online via the Microsoft Graph API and Azure AD App Registrations (MSAL), prospective employers and technical evaluators testing the repository offline or in sandbox environments will not have access to a corporate Microsoft 365 tenant.

## Decision
We implemented a **Provider Pattern** with a `DocumentationProvider` abstract interface:
1. **`SharePointGraphProvider`**: Production client using MSAL Python to obtain OAuth2 client-credential bearer tokens (`https://graph.microsoft.com/.default`), create items in SharePoint Lists ("ITSM Operational Improvement Tracker"), and upload markdown/PDF reports into SharePoint Document Libraries.
2. **`LocalDocumentProvider`**: High-fidelity local mirror storing list state in structured JSON and reports in a dedicated document directory.
3. Both providers share the exact same interface and data contracts, selectable via `DOCUMENTATION_PROVIDER=local|graph` in `.env`.

## Consequences
- Codebase contains 100% production-ready Microsoft Graph API code.
- Zero-friction demo and testability: anyone cloning the repository can run the entire workflow offline and inspect generated reports and list records immediately.
