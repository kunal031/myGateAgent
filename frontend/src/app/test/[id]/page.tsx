import ExamRunner from "@/features/exam/ExamRunner";

export default async function ExamPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ExamRunner examId={Number(id)} />;
}
