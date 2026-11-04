---
name: Ploptimizer assembly benchmark
description: A readable scientific result matrix with evidence pages.
colors:
  ink: "#182d31"
  muted: "#526469"
  primary: "#075e63"
  paper: "#f6f8f7"
  surface: "#ffffff"
  line: "#d7e1de"
  pass: "#176344"
  fail: "#9e302a"
  pending: "#74540d"
typography:
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "16px"
    lineHeight: 1.6
  display:
    fontSize: "clamp(1.9rem, 4vw, 2.7rem)"
    fontWeight: 680
    lineHeight: 1.18
    letterSpacing: "-0.03em"
spacing:
  group: "24px"
  section: "40px"
---

## Overview

Follow the user's simple scientific-table brief: a result matrix, scenario pages
and methods. Use a quiet light surface, dark text and restrained teal navigation.

## Colors

Status colours supplement visible text; scientific failures and execution errors
remain distinct labels even when both use the failure colour.

## Typography

Use the familiar system sans stack for this operating interface. Use tabular
figures for measured data and monospace only for accessions, commands and hashes.

## Layout

Limit content to 1220 px. Keep prose to 75 characters per line. The matrix scrolls
inside its own labelled region on small screens; navigation and prose fit the
viewport. Preserve the same routes and semantics across screen sizes.

## Elevation & Depth

Flat surfaces, simple rules and no decorative shadows or imagery.

## Components

The matrix is a semantic table with row/column headers and a caption. Each result
links to its scenario section. Status text is always present. Scenario inputs,
run evidence and scoring limits remain visible without scripts.
