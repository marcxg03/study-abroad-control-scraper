# Project Brief: Reddit Control Group Scraper

## What We're Building
A local Streamlit web app that helps lab members identify Reddit control group users across three predefined groups, then scrapes the complete post history of every identified user and exports the results as a CSV file ready for analysis in R or Python.

## Who It's For
Research lab members who are comfortable opening a terminal and running a local Python app. Not a consumer product — an internal research tool built for speed and reliability.

## The Three Hardcoded Groups
1. **Primary External Control** — r/studyAbroad users who posted exactly once OR used cancellation-related keywords in their posts
2. **Secondary External Control A** — random sample of r/REU users
3. **Secondary External Control B** — random sample of r/college users

## What "Done" Looks Like
A CSV file with one row per post, covering the complete Reddit history (no time boundary) of every identified user across all subreddits.

## Key Constraints
- Built in Streamlit, runs locally
- Scraping runs in the background — lab member can walk away and return when it's finished
- ArcticShift API is the data source — setup/authentication needs to be documented as part of the build
- Target: at least 500 users per group

## Out of Scope for Now
- Hosted/deployed version
- Flexibility to add new groups or subreddits
- Any analysis of the data — this tool only collects it
