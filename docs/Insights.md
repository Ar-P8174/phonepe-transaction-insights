# PhonePe Transaction Insights

## Key findings

**Scale and momentum.** PhonePe processed 128.5 billion transactions worth about ₹155 lakh crore in 2025. Quarterly volume reached 38.7 billion in Q2 2026. Registered users stand at 712 million and merchants at 50.7 million.

**Growth is maturing.** Year-on-year growth in 2025 was 34% for retail, 23.9% for P2P and 15.5% for utility, down sharply from 2022 levels. Targets built on past growth rates will be missed; revenue per transaction becomes the better yardstick.

**Commerce now leads.** Retail is 61.9% of 2025 transactions. P2P transfers, historically the entry point for new users, are about a third.

**Concentration.** The five largest states hold 53.3% of lifetime transactions, led by Maharashtra and Karnataka. Bengaluru Urban alone moved about ₹7.9 lakh crore in 2025, more than double the next district (Pune).

**Engagement gap.** Telangana makes 106 transactions per registered user per quarter; Manipur makes 12, a 8.7x gap. Users and transactions are almost perfectly correlated across states, so the lever is activity per user, not user counts.

**District segments.** 210 'everyday spender' districts produce 45.4% of 2025 value and 182 power hubs 35.4%. 181 emerging districts hold 134.9 million users but contribute only 10.7% of value.

**Kerala.** Kerala has the slowest three-year growth of all 36 states (28.5% a year versus Lakshadweep's 106.4%, from a tiny base), and ranks 34 of 36 on engagement.

**Merchant density.** Delhi has 89.1 merchants per 1,000 users; Ladakh has 10.7. Thin networks limit retail growth.

**Anomaly screening.** 20 district-quarters show average ticket sizes more than 3 standard deviations above normal (top: Shi Yomi, Arunachal Pradesh, z = 7.32). These are signals for review, not proof of fraud.

## Recommendations

1. Activate before acquiring: target the emerging-district segment with first-use incentives.
2. Close the merchant gap: prioritise onboarding where merchants per 1,000 users is lowest and P2P share is highest.
3. Defend the core: concentrate merchant products (QR, soundbox, credit) on the top districts.
4. Investigate Kerala (and Tamil Nadu): commission competitor and user research before setting budgets.
5. Plan for Q2 softness and for slower growth: schedule campaigns in Q2 and track revenue per transaction.
6. Route anomaly flags to risk teams as a screening input only.
7. Cross-sell credit and insurance in high-ticket, low-frequency states.

## Data notes and limitations

- Source: PhonePe Pulse open data (github.com/PhonePe/pulse), Q1 2018 to Q2 2026, 36 states and UTs, 783 districts.
- The project brief mentions insurance and pin-code data. The current Pulse release has neither, so merchant data replaces insurance and district is the finest geography.
- Transaction amounts exist only at district level. Registered users and merchants are cumulative stocks and include inactive accounts.
- Growth rates use full calendar years only (2026 has two quarters). Seasonality rests on seven yearly observations and includes the 2020 lockdown.
- The anomaly query is a statistical screen, not a fraud finding. No competitor data exists in the dataset, so competitive statements are out of scope.
