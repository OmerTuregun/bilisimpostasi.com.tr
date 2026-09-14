/** Vitest stub — production code imports `astro:content`; unit tests never hit the real API. */
export async function getCollection(_name: string): Promise<unknown[]> {
  return [];
}

export type CollectionEntry<_T extends string = string> = {
  id: string;
  data: Record<string, unknown>;
};
