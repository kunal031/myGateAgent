// See the note in ../page.tsx: a submitted paper is fetched at runtime.
export const instant = false;

import ExamResult from "@/features/exam/ExamResult";

export default async function ResultPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ExamResult examId={Number(id)} />;
}
