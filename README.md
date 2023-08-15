# automation-metadata-collector
Gathers information from PANW automation GitHub repos to build documentation for pan.dev

## Frontmatter

Automation Hub Metadata is collected dynamically without need to set it in the
README. However, the values collected can be overridden in the README
frontmatter.

### Overrides
```
title:
What shows in the browser tab header
Default is first header in README

cloudId: (aws|azure|gcp)
Override the cloud, probably should never do this
Default is taken from repo name

short_title:
The name that shows in the sidebar
Default is synthesized from the module/example directory name

type: (module|example|refarch)
Override what the README is for
Default is 'module' if in modules directory, 'example' if in examples directory

description:
Set the description that shows in the card for each module in the index pages
Default is the first line in the readme after the first header

show_in_hub: (true|false)
Override if this should show up in the Automation Hub at all
Default is true for modules and refarchs, false for examples
```

For example, here is a README file that `overrides` the `short_title`, type, and
`description`.

```yaml
---
short_title: Combined Model
type: refarch
description: Deploy to AWS using the Combined model reference architecture
---
# Reference Architecture: VM-Series for AWS Combined Model

The rest of the README text...
```