"use client";

import { createContext, useContext } from "react";

export interface Me {
  id: number;
  name: string;
  role: string;
  sponsor: boolean;
}

const Ctx = createContext<Me | null>(null);

export function SessionProvider({ me, children }: { me: Me; children: React.ReactNode }) {
  return <Ctx.Provider value={me}>{children}</Ctx.Provider>;
}

/** The signed-in user. Sponsors can update any milestone; site staff only the ones they own. */
export function useMe() {
  const me = useContext(Ctx);
  return {
    me,
    canEdit: (ownerId: number | null | undefined) => !!me && (me.sponsor || (ownerId != null && ownerId === me.id)),
  };
}
