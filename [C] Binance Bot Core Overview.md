---
type: problems
date: 2026-05-08
project: Binance Bot Core
---

## Goal
Set up the project structure, connect to the Binance API, and get live price data flowing — a working Python foundation to build the trading bot on.

## Why
Generate passive income while working a day job. The bot handles trading so Holy doesn't have to watch the market 24/7.

## Tangible Outcomes
- Bot connects to Binance API and authenticates successfully
- Pulls live price data for selected trading pairs
- Can place test orders on Binance Testnet (paper trading)
- Runs locally without crashing
- Logs activity and errors to a file

## Open Problems
1. How to use the Binance Testnet to safely train the algo and practice trading logic before going live
2. What strategy logic can realistically deliver consistent returns — and how to measure performance (target: 50%+ weekly gain, understand the risks involved)
3. How to handle API rate limits and connection errors gracefully
4. Which trading pairs to start with on testnet
5. How to structure the codebase so strategy logic is easy to swap out later
