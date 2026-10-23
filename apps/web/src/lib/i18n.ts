// Interface strings for the answer-check pages, in English and Hindi.
// Exam content (question text, model answer) keeps the language of its source paper.

export type Lang = "en" | "hi";

export const LANG_STORAGE_KEY = "uppsc-ui-language";

const en = {
  appName: "UPPSC BEO Mains",
  pageTitle: "Answer sheet check",
  pageLead: "Choose a question, upload your handwritten answer sheet, and see your marks with what to improve.",
  languageLabel: "Language",

  stepQuestion: "Choose question",
  stepUpload: "Upload sheet",
  stepResult: "Your result",

  paperHeading: "Choose the paper",
  paperHelp: "Pick the paper your answer belongs to.",
  papersError: "The papers could not be loaded. Please try again in a moment.",
  loadingPapers: "Loading papers…",
  questionHeading: "Choose the question",
  questionHelp: "Pick the question you answered. Only that answer will be checked.",
  questionsError: "The questions could not be loaded. Please try again.",
  loadingQuestions: "Loading questions…",
  marks: "{n} marks",
  wordLimit: "Word limit {n}",
  back: "Back",
  next: "Next",

  uploadHeading: "Upload your answer sheet",
  uploadHelp:
    "PDF, PNG or JPG, up to 25 MB. Write the question number before your answer, for example 1 or 1(a). Scan or photograph every page of the answer.",
  chooseFile: "Choose file",
  dropHint: "or drop the file here",
  selectedFile: "Selected file",
  fileTooLarge: "This file is larger than 25 MB.",
  fileType: "Upload a PDF, PNG or JPG file.",
  start: "Start",
  checking:
    "Reading your sheet and checking the answer. A long sheet can take several minutes. Please keep this page open.",
  checkFailed: "The answer could not be checked. Please upload a clear PDF, PNG or JPG and try again.",

  scoreLabel: "Your marks",
  outOf: "out of {n}",
  statusGood: "Good answer",
  statusPartial: "Partly correct",
  statusLow: "Needs more work",
  statusReview: "Needs your check",
  statusNone: "Not answered",
  feedbackHeading: "Overall",
  goodHeading: "What you did well",
  goodEmpty: "No specific strong points were found in this answer.",
  missingHeading: "What is missing compared with the model answer",
  missingEmpty: "All the main points are covered.",
  modelHeading: "Model answer",
  modelHelp: "A model answer for this question, prepared from the paper's expected points.",
  readHeading: "Text read from your sheet",
  readHelp: "Check that this is what you wrote. If it is wrong, write more clearly and upload again.",
  noAnswer:
    "We could not find an answer to this question on the sheet. Check that the question number is written before the answer, then upload again.",
  noteDisagree: "The two checks gave different results. Please confirm the marks.",
  noteHeader: "The question number on the sheet was hard to read. Please confirm this answer belongs to this question.",
  noteSingle: "Checked by one method only. Please confirm the marks.",
  noteWordLimit: "The answer is longer than the word limit. Marks were not reduced for length.",
  noteFallbackReader: "Some pages were read with the basic reader, so the text may be less accurate.",
  guide: "This result is an automatic guide. A teacher should confirm the marks before they are final.",
  checkAnother: "Check another question",
  startOver: "Start over",
  accessLabel: "Access code",
  accessHelp: "Enter the access code given by your coaching centre or examiner.",
  accessWrong: "The access code is not correct. Please check it and try again.",
};

const hi: typeof en = {
  appName: "UPPSC BEO मेन्स",
  pageTitle: "उत्तर-पत्र जाँच",
  pageLead: "प्रश्न चुनें, हस्तलिखित उत्तर-पत्र अपलोड करें, और अपने अंक तथा सुधार के बिंदु देखें।",
  languageLabel: "भाषा",

  stepQuestion: "प्रश्न चुनें",
  stepUpload: "उत्तर-पत्र अपलोड",
  stepResult: "आपका परिणाम",

  paperHeading: "प्रश्नपत्र चुनें",
  paperHelp: "वह प्रश्नपत्र चुनें जिसका उत्तर आपने लिखा है।",
  papersError: "प्रश्नपत्र लोड नहीं हो सके। कृपया थोड़ी देर बाद फिर प्रयास करें।",
  loadingPapers: "प्रश्नपत्र लोड हो रहे हैं…",
  questionHeading: "प्रश्न चुनें",
  questionHelp: "वह प्रश्न चुनें जिसका उत्तर आपने दिया है। केवल वही उत्तर जाँचा जाएगा।",
  questionsError: "प्रश्न लोड नहीं हो सके। कृपया फिर प्रयास करें।",
  loadingQuestions: "प्रश्न लोड हो रहे हैं…",
  marks: "{n} अंक",
  wordLimit: "शब्द सीमा {n}",
  back: "पीछे",
  next: "आगे",

  uploadHeading: "अपना उत्तर-पत्र अपलोड करें",
  uploadHelp:
    "PDF, PNG या JPG, 25 MB तक। उत्तर से पहले प्रश्न संख्या लिखें, जैसे 1 या 1(a)। उत्तर-पत्र का हर पृष्ठ स्कैन या फोटो करें।",
  chooseFile: "फ़ाइल चुनें",
  dropHint: "या फ़ाइल यहाँ छोड़ें",
  selectedFile: "चुनी गई फ़ाइल",
  fileTooLarge: "यह फ़ाइल 25 MB से बड़ी है।",
  fileType: "PDF, PNG या JPG फ़ाइल अपलोड करें।",
  start: "शुरू करें",
  checking:
    "उत्तर-पत्र पढ़ा जा रहा है और उत्तर की जाँच हो रही है। लंबे उत्तर-पत्र में कई मिनट लग सकते हैं। कृपया यह पेज खुला रखें।",
  checkFailed: "उत्तर की जाँच नहीं हो सकी। कृपया साफ़ PDF, PNG या JPG अपलोड करके फिर प्रयास करें।",

  scoreLabel: "आपके अंक",
  outOf: "{n} में से",
  statusGood: "अच्छा उत्तर",
  statusPartial: "आंशिक रूप से सही",
  statusLow: "और सुधार की ज़रूरत",
  statusReview: "आपकी जाँच आवश्यक",
  statusNone: "उत्तर नहीं मिला",
  feedbackHeading: "कुल मिलाकर",
  goodHeading: "आपने क्या अच्छा किया",
  goodEmpty: "इस उत्तर में कोई विशेष अच्छा बिंदु नहीं मिला।",
  missingHeading: "मॉडल उत्तर की तुलना में क्या छूटा है",
  missingEmpty: "मुख्य बिंदु सभी शामिल हैं।",
  modelHeading: "मॉडल उत्तर",
  modelHelp: "इस प्रश्न का मॉडल उत्तर, प्रश्नपत्र के अपेक्षित बिंदुओं से तैयार किया गया।",
  readHeading: "आपके उत्तर-पत्र से पढ़ा गया पाठ",
  readHelp: "जाँचें कि यही आपने लिखा है। यदि गलत है, तो साफ़ लिखकर फिर अपलोड करें।",
  noAnswer:
    "इस प्रश्न का उत्तर उत्तर-पत्र पर नहीं मिला। जाँचें कि उत्तर से पहले प्रश्न संख्या लिखी है, फिर से अपलोड करें।",
  noteDisagree: "दोनों जाँचों के परिणाम अलग हैं। कृपया अंकों की पुष्टि करें।",
  noteHeader: "उत्तर-पत्र पर प्रश्न संख्या स्पष्ट नहीं थी। कृपया पुष्टि करें कि यह उत्तर इसी प्रश्न का है।",
  noteSingle: "जाँच केवल एक तरीके से हुई। कृपया अंकों की पुष्टि करें।",
  noteWordLimit: "उत्तर शब्द सीमा से लंबा है। लंबाई के कारण अंक नहीं घटाए गए।",
  noteFallbackReader: "कुछ पृष्ठ बुनियादी रीडर से पढ़े गए, इसलिए पाठ कम सटीक हो सकता है।",
  guide: "यह परिणाम स्वचालित मार्गदर्शन है। अंक अंतिम होने से पहले शिक्षक को पुष्टि करनी चाहिए।",
  checkAnother: "दूसरा प्रश्न जाँचें",
  startOver: "फिर से शुरू करें",
  accessLabel: "एक्सेस कोड",
  accessHelp: "अपने कोचिंग केंद्र या परीक्षक से मिला एक्सेस कोड दर्ज करें।",
  accessWrong: "एक्सेस कोड सही नहीं है। कृपया जाँचकर फिर प्रयास करें।",
};

export type Dict = typeof en;
export type Key = keyof Dict;

export const STRINGS: Record<Lang, Dict> = { en, hi };

export function translate(lang: Lang, key: Key, vars?: Record<string, string | number>): string {
  let text = STRINGS[lang][key] ?? STRINGS.en[key];
  if (vars) {
    for (const [k, v] of Object.entries(vars)) text = text.replace(`{${k}}`, String(v));
  }
  return text;
}
