// See the note in ../page.tsx.
export const instant = false;

import ExamResult from "@/features/exam/ExamResult";

export default async function QuizResultPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ExamResult examId={Number(id)} />;
}
