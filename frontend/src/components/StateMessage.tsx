/** Centered loading, empty, or error copy. */
export function StateMessage({ title, body }: { title: string; body: string }) {
  return (
    <div className="grid h-full place-items-center px-6 text-center">
      <div>
        <h2 className="font-serif text-2xl text-ink">{title}</h2>
        <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-stone-600">{body}</p>
      </div>
    </div>
  );
}
