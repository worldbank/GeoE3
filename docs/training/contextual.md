## ![](../images/topics/contextual.svg){ width="28" style="vertical-align:middle;margin-right:0.4rem;" } Contextual

!!! abstract "Learning objective"
    By the end of this page you'll be able to configure all four
    Contextual-dimension factors, understand why they're entered as a
    single national number rather than a spatial dataset, and know which
    published index backs each one.

The Contextual Dimension refers to the laws and policies that shape
workplace gender discrimination, financial autonomy, and overall gender
empowerment. Although this dimension may vary between countries due to
differences in legal frameworks, it remains consistent within a single
country, as national policies and regulations are typically applied
uniformly across countries. For more information on data input used
from open sources, see the [Getting Data
tutorial](datacollection.md#tutorial-manual-national-index-score-entry).

![National Index Score technique: one published value filled across every cell](../images/methodology/index_score.svg){ style="float:right;width:96px;margin:0 0 0.75rem 1rem;" }

Every Contextual factor uses the **National Index Score** technique (see
[Processor Types](processor-types.md#national-index-score)): a researched national score
typed straight into the factor's dialog, no spatial dataset involved.
Configure each one using the pattern from [Configuring
Items](configuring-items.md#the-generic-pattern): double-click, enter the
score, then right-click → **Run Item Workflow**. See [Getting
Data](datacollection.md#tutorial-manual-national-index-score-entry) for
how that number is calculated and entered.

### Input Contextual factors

---

#### ![](../images/topics/eplex.svg){ width="22" style="vertical-align:middle;margin-right:0.4rem;" } Generic analysis: the EPLEX score

EPLEX is a summary measure of Employment Protection Legislation (EPL)
stringency, created by the International Labour Organization (ILO),
that measures how strongly a country's laws protect workers against
dismissal at the initiative of an employer.

![Contextual Weights](../images/new%20images/Contextual_dm.jpg){ width="75%" }

Enter the EPLEX score as a fraction between 0 and 1 (the tool multiplies
it by 5 to put it on the usual 0–5 scale); if you already have a value
on the 0–5 scale from an older project, you can enter that directly and
it's used as-is.

---

#### Women's Enabling Environments analysis: the WBL database

For a Women's Enabling Environments analysis, GeoE3 uses data from the
WBL (Women, Business and the Law) database instead:

![](../images/topics/workplace_discrimination.svg){ width="22" style="vertical-align:middle;margin-right:0.4rem;" }
**Workplace Discrimination** involves laws that address gender biases
and stereotypes that hinder women's career advancement, especially in
male-dominated fields. It's obtained from the Workplace Index score of
the WBL.

![](../images/topics/regulatory_frameworks.svg){ width="22" style="vertical-align:middle;margin-right:0.4rem;" }
**Regulatory Frameworks** pertain to laws and policies that protect
women's employment rights, such as childcare support and parental
leave, influencing their workforce participation. This indicator is
composed by the Pay and Parenthood Index score of the WBL database.

![](../images/topics/financial_inclusion.svg){ width="22" style="vertical-align:middle;margin-right:0.4rem;" }
**Financial Inclusion** involves laws concerning women's access to
financial resources like loans and credit, which is crucial for
starting businesses and investing in economic opportunities. This
indicator is composed by the Entrepreneurship Index score of the WBL
2024.

The WBL index scores are already 0–100, so you enter the published value
directly and GeoE3 converts it to the usual 0–5 scale for you:

| WBL score | GeoE3 score | Colour |
|---|---|---|
| 95 – 100 | 5 | <span style="display:inline-block;width:14px;height:14px;background:#2c7bb6;border:1px solid #0003;border-radius:2px;"></span> |
| 90 – 94 | 4 | <span style="display:inline-block;width:14px;height:14px;background:#bce1b8;border:1px solid #0003;border-radius:2px;"></span> |
| 80 – 89 | 3 | <span style="display:inline-block;width:14px;height:14px;background:#ffffbf;border:1px solid #0003;border-radius:2px;"></span> |
| 75 – 79 | 2 | <span style="display:inline-block;width:14px;height:14px;background:#fdae61;border:1px solid #0003;border-radius:2px;"></span> |
| 60 – 74 | 1 | <span style="display:inline-block;width:14px;height:14px;background:#d7191c;border:1px solid #0003;border-radius:2px;"></span> |
| 0 – 59 | 0 | <span style="display:inline-block;width:14px;height:14px;background:#d7191c;border:1px solid #0003;border-radius:2px;"></span> |

As a rough feel for the scale: a country with strongly enabling
legislation would score in the 90s; something clearly below that
reflects whatever gap you've identified in your research.

---

Once every factor has a value, double-click the **Contextual** dimension
and follow the same [generic pattern](configuring-items.md#the-generic-pattern)
as every other item in the tree: assign weights, balance them, and run
it.

![Contextual Final Output](../images/new%20images/Contextual_dm1.jpg){ width="75%" }

The outputs (Workplace Discrimination, Regulatory Frameworks and
Financial Inclusion, plus their aggregation into the final Contextual
score) land in the Contextual folder within your project folder, on the
usual [0–5 enablement scale](the-model.md#the-05-likert-scale).

!!! success "Recap"
    - All four Contextual factors (EPLEX Score for a generic analysis;
      Workplace Discrimination, Regulatory Frameworks and Financial
      Inclusion for a Women's Enabling Environments analysis) are entered
      as a single national number, not a spatial dataset.
    - Workplace Discrimination, Regulatory Frameworks and Financial
      Inclusion map to three different WBL 2024 sub-indices (the
      Workplace, Pay and Parenthood, and Entrepreneurship index scores
      respectively). Don't reuse the same number for all three.
    - Results combine into a single Contextual output on the usual 0–5
      enablement scale, viewable as a mutually-exclusive layer group.
