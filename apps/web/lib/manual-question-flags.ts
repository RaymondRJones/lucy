type FlagQuestion = {
  id: string;
  label: string;
  pdf_ref?: string;
};

type FlagPage = {
  id: string;
  title: string;
  questions: FlagQuestion[];
};

export type ManualQuestionFlags = Record<string, true>;

export type ManualQuestionFlagSummary = {
  pageId: string;
  pageTitle: string;
  questionId: string;
  label: string;
  pdfRef?: string;
};

export function normalizeManualQuestionFlags(value: Record<string, unknown> | undefined): ManualQuestionFlags {
  return Object.fromEntries(Object.entries(value ?? {}).filter(([, flag]) => Boolean(flag)).map(([id]) => [id, true]));
}

export function manualFlagsForPage(page: FlagPage, flags: ManualQuestionFlags): ManualQuestionFlags {
  return Object.fromEntries(page.questions.filter((question) => flags[question.id]).map((question) => [question.id, true]));
}

export function manualFlagCountForPage(page: FlagPage, flags: ManualQuestionFlags) {
  return page.questions.filter((question) => flags[question.id]).length;
}

export function manualFlagSummaries(pages: FlagPage[], flags: ManualQuestionFlags): ManualQuestionFlagSummary[] {
  return pages.flatMap((page) =>
    page.questions
      .filter((question) => flags[question.id])
      .map((question) => ({
        pageId: page.id,
        pageTitle: page.title,
        questionId: question.id,
        label: question.label,
        pdfRef: question.pdf_ref,
      })),
  );
}
