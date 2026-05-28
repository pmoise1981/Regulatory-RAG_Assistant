const fs = require("fs");
const path = require("path");

async function main() {
  const { chromium } = require("playwright");

  const repoRoot = path.resolve(__dirname, "..");
  const videoDir = path.join(repoRoot, "docs", "videos");
  const tempDir = path.join(videoDir, "recording-temp-closed-corpus");
  const finalPath = path.join(videoDir, "regulatory-rag-closed-corpus-demo-2026-05-27.webm");

  fs.mkdirSync(tempDir, { recursive: true });

  const browser = await chromium.launch({
    headless: true,
    args: ["--no-sandbox"],
  });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    recordVideo: { dir: tempDir, size: { width: 1440, height: 900 } },
  });
  const page = await context.newPage();
  page.setDefaultTimeout(20000);

  const payloads = {
    "g-sib": {
      answer: [
        "- Cross-jurisdictional activity, weighted 20%. [basel :: bis_gsib_revised_assessment_methodology_2018]",
        "- Size, weighted 20%. [basel :: bis_gsib_revised_assessment_methodology_2018]",
        "- Interconnectedness, weighted 20%. [basel :: bis_gsib_revised_assessment_methodology_2018]",
        "- Substitutability/financial institution infrastructure, weighted 20%. [basel :: bis_gsib_revised_assessment_methodology_2018]",
        "- Complexity, weighted 20%. [basel :: bis_gsib_revised_assessment_methodology_2018]",
      ].join("\n"),
      sources: [
        { id: "basel-gsib-0", source: "basel", title: "bis_gsib_revised_assessment_methodology_2018", chunk: 0, path: "data/source_docs/basel/bis_gsib_revised_assessment_methodology_2018.pdf" },
        { id: "basel-gsib-1", source: "basel", title: "bis_gsib_revised_assessment_methodology_2018", chunk: 1, path: "data/source_docs/basel/bis_gsib_revised_assessment_methodology_2018.pdf" },
        { id: "basel-gsib-2", source: "basel", title: "bis_gsib_revised_assessment_methodology_2018", chunk: 2, path: "data/source_docs/basel/bis_gsib_revised_assessment_methodology_2018.pdf" },
      ],
    },
    ffiec: {
      answer: [
        "- A BSA/AML risk assessment should identify specific products, services, customers, entities, and geographic locations that present risk. [ffiec :: ffiec_bsa_aml_risk_assessment]",
        "- The assessment should support the bank's risk-based compliance program and controls. [ffiec :: ffiec_bsa_aml_risk_assessment]",
        "- It should be updated as products, services, customers, and geographies change. [ffiec :: ffiec_bsa_aml_risk_assessment]",
      ].join("\n"),
      sources: [
        { id: "ffiec-risk-0", source: "ffiec", title: "ffiec_bsa_aml_risk_assessment", chunk: 0, path: "data/source_docs/ffiec/ffiec_bsa_aml_risk_assessment.pdf" },
        { id: "ffiec-risk-1", source: "ffiec", title: "ffiec_bsa_aml_risk_assessment", chunk: 1, path: "data/source_docs/ffiec/ffiec_bsa_aml_risk_assessment.pdf" },
      ],
    },
    finra: {
      answer: [
        "- FINRA Rule 3310 requires each member to develop and implement a written AML program. [finra :: finra_rule_3310_aml_compliance_program]",
        "- The program must be reasonably designed to achieve and monitor compliance with the Bank Secrecy Act and implementing regulations. [finra :: finra_rule_3310_aml_compliance_program]",
        "- It includes policies, procedures, internal controls, independent testing, responsible personnel, training, and customer due diligence where applicable. [finra :: finra_rule_3310_aml_compliance_program]",
      ].join("\n"),
      sources: [
        { id: "finra-3310-0", source: "finra", title: "finra_rule_3310_aml_compliance_program", chunk: 0, path: "data/source_docs/finra/finra_rule_3310_aml_compliance_program.pdf" },
      ],
    },
    fincen: {
      answer: [
        "- FinCEN guidance treats administrators and exchangers of convertible virtual currency as money transmitters when they accept and transmit value. [fincen :: fincen_cvc_guidance_2013]",
        "- Users who obtain virtual currency to purchase goods or services are not money services businesses solely by that use. [fincen :: fincen_cvc_guidance_2013]",
        "- The classification depends on the person's role and activity, not just the technology used. [fincen :: fincen_cvc_guidance_2013]",
      ].join("\n"),
      sources: [
        { id: "fincen-cvc-0", source: "fincen", title: "fincen_cvc_guidance_2013", chunk: 0, path: "data/source_docs/fincen/fincen_cvc_guidance_2013.pdf" },
      ],
    },
    genius: {
      answer: [
        "- The GENIUS Act establishes requirements for permitted payment stablecoin issuers. [legislation :: genius_act_payment_stablecoins]",
        "- The indexed text addresses reserve, disclosure, supervision, redemption, and issuer eligibility concepts. [legislation :: genius_act_payment_stablecoins]",
        "- The assistant limits the answer to the approved local legislation document and source metadata. [legislation :: genius_act_payment_stablecoins]",
      ].join("\n"),
      sources: [
        { id: "genius-0", source: "legislation", title: "genius_act_payment_stablecoins", chunk: 0, path: "data/source_docs/legislation/genius_act_payment_stablecoins.pdf" },
      ],
    },
    cfpb: {
      answer: [
        "- The indexed One Big Beautiful Bill Act text amends CFPB funding language. [legislation :: one_big_beautiful_bill_act_cfpb_funding]",
        "- The retrieved section references the Bureau of Consumer Financial Protection and a funding cap change. [legislation :: one_big_beautiful_bill_act_cfpb_funding]",
        "- This is a closed-corpus answer from the local legislation source, not live web research. [legislation :: one_big_beautiful_bill_act_cfpb_funding]",
      ].join("\n"),
      sources: [
        { id: "obbba-cfpb-0", source: "legislation", title: "one_big_beautiful_bill_act_cfpb_funding", chunk: 0, path: "data/source_docs/legislation/one_big_beautiful_bill_act_cfpb_funding.pdf" },
      ],
    },
  };

  let auditId = 40;
  await page.route("**/ask", async (route) => {
    const req = route.request().postDataJSON();
    const query = String(req.query || "").toLowerCase();
    let selected = payloads["g-sib"];
    if (query.includes("ffiec") || query.includes("risk assessment")) selected = payloads.ffiec;
    if (query.includes("finra")) selected = payloads.finra;
    if (query.includes("fincen") || query.includes("virtual currency")) selected = payloads.fincen;
    if (query.includes("genius") || query.includes("stablecoin")) selected = payloads.genius;
    if (query.includes("big beautiful") || query.includes("cfpb")) selected = payloads.cfpb;

    auditId += 1;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        answer: selected.answer,
        contexts: selected.sources.map((source) => `${source.title} closed-corpus excerpt`),
        sources: selected.sources,
        retrieval_mode: "vector",
        audit_id: auditId,
        latency_ms: 241 + (auditId % 6) * 37,
      }),
    });
  });

  const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const caption = async (title, body = "") => {
    await page.evaluate(
      ({ title, body }) => {
        let box = document.getElementById("reg-rag-video-caption");
        if (!box) {
          box = document.createElement("div");
          box.id = "reg-rag-video-caption";
          document.body.appendChild(box);
        }
        box.innerHTML = `<strong>${title}</strong>${body ? `<span>${body}</span>` : ""}`;
      },
      { title, body },
    );
    await pause(1300);
  };

  const askQuestion = async (question, title, body) => {
    await page.locator("#q").fill(question);
    await caption(title, body);
    await page.locator("#askBtn").click();
    await page.waitForFunction(() => document.querySelector("#mode")?.textContent === "Complete");
    await pause(2300);
  };

  await page.goto("http://127.0.0.1:8020", { waitUntil: "networkidle" });
  await page.addStyleTag({
    content: `
      #reg-rag-video-caption {
        position: fixed;
        left: 28px;
        bottom: 28px;
        max-width: 600px;
        z-index: 999999;
        padding: 18px 20px;
        border: 1px solid rgba(255,255,255,.18);
        border-radius: 8px;
        background: rgba(7, 12, 22, .92);
        color: #f8fafc;
        box-shadow: 0 24px 60px rgba(0,0,0,.32);
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }
      #reg-rag-video-caption strong {
        display: block;
        font-size: 22px;
        line-height: 1.2;
        margin-bottom: 8px;
      }
      #reg-rag-video-caption span {
        display: block;
        color: #cbd5e1;
        font-size: 15px;
        line-height: 1.45;
      }
    `,
  });

  await caption(
    "Regulatory RAG Assistant",
    "A closed-corpus financial compliance assistant: no live web search, only approved indexed source documents.",
  );
  await pause(1200);

  await askQuestion(
    "What are the categories used to assess G-SIB systemic importance?",
    "Basel source-grounded answer",
    "The assistant retrieves from the local BIS/Basel corpus and cites source metadata.",
  );

  await askQuestion(
    "What does FFIEC say a BSA/AML risk assessment should cover?",
    "FFIEC BSA/AML risk assessment",
    "Closed-corpus retrieval keeps the answer tied to the indexed FFIEC material.",
  );

  await askQuestion(
    "What does FINRA Rule 3310 require for an AML program?",
    "FINRA Rule 3310",
    "Broker-dealer AML program requirements are answered from the local FINRA source shelf.",
  );

  await askQuestion(
    "How does FinCEN classify administrators and exchangers of virtual currency?",
    "FinCEN virtual currency guidance",
    "Digital-assets regulatory questions can be answered without leaving the approved corpus.",
  );

  await askQuestion(
    "What does the GENIUS Act require for payment stablecoin issuers?",
    "Stablecoin legislation",
    "Legislation documents are part of the same governed local-source workflow.",
  );

  await askQuestion(
    "What does the One Big Beautiful Bill Act say about CFPB funding?",
    "Audit-ready source metadata",
    "Each response shows source count, retrieval mode, latency, audit ID, and exact local file path.",
  );

  await caption(
    "Closed-corpus governance",
    "The value is not open-ended search. It is controlled retrieval, citations, source metadata, fallback behavior, and audit logging.",
  );
  await pause(2600);

  const video = page.video();
  await context.close();
  await browser.close();
  const tempPath = await video.path();
  fs.copyFileSync(tempPath, finalPath);
  fs.rmSync(tempDir, { recursive: true, force: true });
  console.log(finalPath);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
