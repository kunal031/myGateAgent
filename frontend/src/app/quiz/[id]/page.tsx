// A quiz session is fetched at runtime, so there is nothing to prerender.
export const instant = false;

import QuizRunner from "@/features/exam/QuizRunner";

export default async function QuizSessionPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <QuizRunner quizId={Number(id)} />;
}
