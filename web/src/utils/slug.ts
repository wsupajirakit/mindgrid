/** A short name (lowercase letters, digits, dashes) suggested from a display name; empty
 * when the name has no Latin letters or digits (the user types one then). */
export function suggestSlug(name: string, max = 64): string {
  return name.toLowerCase().normalize('NFKD')
    .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, max)
}
