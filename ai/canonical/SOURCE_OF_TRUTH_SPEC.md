# SOURCE OF TRUTH — Experian Technical Exercise

**Authority:** This file is the canonical authority for the take-home.

If any prompt, skill, role description, best-practice guide, previous design decision, AI suggestion, or external source conflicts with this specification, **this specification wins**, unless Experian provides a later explicit clarification.

---

## Technical Exercise: Build a Small End-to-End Data Workflow

Design and implement a small end-to-end data workflow using a dataset of your choice.

You may use publicly available or synthetic data. Please do not use confidential, proprietary or personal data.

### 1. Data Ingestion and Processing

Select a dataset and build a data-processing workflow that:

- ingests data from one or more sources;
- uses Python and/or SQL to process and transform the data;
- produces a structured, analytics-ready output;
- demonstrates appropriate data modelling and transformation choices; and
- can be rerun consistently.

Please explain the key decisions you make and any assumptions or limitations associated with your approach.

### 2. Data Quality and Validation

Consider what data-quality and validation controls are appropriate for your chosen dataset and workflow.

Implement the controls you consider necessary and be prepared to explain:

- why you selected them;
- what risks they address;
- how you determine whether the resulting data is fit for use; and
- how your workflow should respond when a validation check identifies an issue.

We are interested in your judgement in identifying the appropriate controls rather than the number of checks implemented.

### 3. Traceability and Reproducibility

Consider how another engineer could understand, maintain and reproduce your workflow.

Your approach should address how you would maintain appropriate traceability of:

- source data;
- transformations and processing;
- relevant execution information; and
- historical results where appropriate.

Please explain any design decisions you make in this area.

### 4. Analysis and Presentation

Use the processed data to identify a small number of useful observations or insights.

Present these using an appropriate analytical or visualisation method of your choice, such as Tableau, Power BI or Python.

Your output should:

- communicate the analysis and key insights clearly;
- be well structured and easy to navigate;
- use appropriate visualisations or other analytical presentation techniques;
- demonstrate good attention to layout, readability and visual hierarchy; and
- be presented to a professional standard suitable for business stakeholders.

The primary focus is the quality of the analysis and underlying data solution, but professional presentation is also important. Outputs produced in this role are expected to be clear, well designed and suitable for use with audit and senior business stakeholders, and to follow relevant Experian brand and presentation standards.

### 5. Engineering Approach

Structure your solution as you would for work that may need to be maintained by another engineer.

Consider appropriate engineering practices for:

- code quality and reusability;
- organisation and documentation;
- testing and validation;
- version control;
- error and exception handling; and
- performance and scalability.

Please explain the approach you have taken and any trade-offs you considered.

---

## Use of AI

You are welcome to use AI-assisted tools such as ChatGPT, GitHub Copilot or similar technologies when completing the exercise. Effective use of AI is relevant to how we expect modern data engineering work to be performed.

You remain responsible for the design, correctness and quality of everything you submit.

During the interview, we will discuss how you used AI, where it assisted you, how you evaluated its suggestions and how you validated the resulting solution.

You should therefore be able to:

- explain the code and design decisions in your solution;
- identify assumptions and limitations;
- demonstrate how you established that the results are correct;
- evaluate and challenge AI-generated suggestions where appropriate; and
- modify or adapt your approach when requirements change.

We do not require a transcript of your AI prompts or conversations.

---

## Preparing for the Interview

Please bring your solution in a format that allows you to explain your approach and demonstrate the workflow.

This could include source code or notebooks, SQL scripts, supporting documentation, sample data and outputs, and any visualisations you have created.

Please ensure that your submission contains no confidential, proprietary or personal data.

We recommend spending approximately 2–3 hours on the exercise. We do not expect a production-ready application or extensive infrastructure. Please use the preparation time proportionately across the data engineering, analysis and presentation elements of the exercise.

During the interview, you will be asked to:

- Walk us through your solution and key design decisions.
- Explain how you established that the data and results are reliable.
- Discuss the analysis and how you chose to communicate the results.
- Discuss how you would operationalise, monitor and scale the solution.
- Respond to changes or additional requirements presented during the interview.
- Discuss your use of AI and how you maintained appropriate human oversight.

The assessment focuses on your technical understanding, data engineering and analytical capability, engineering judgement, communication and ability to take ownership of the solution, rather than your ability to recall syntax or build a complex solution within the preparation time.

---

# Authority Order

1. This written exercise.
2. Later explicit Experian clarification.
3. Repository decisions already proven compliant with 1–2.
4. Experian role description.
5. External engineering guidance and public research.
6. AI suggestions.

Lower-priority material may refine a compliant design but may not silently add mandatory scope, redefine success, or delay explicit requirements.

# Mandatory Validation Rule

Every mandatory requirement must map to:

1. implementation or an explicit, justified design decision;
2. concrete verification/evidence;
3. an interview explanation.

A technology merely existing in the repository is **not** evidence that a requirement is satisfied.
