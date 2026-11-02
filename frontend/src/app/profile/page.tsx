"use client";

import React, { Suspense } from "react";

import ProfileView from "@/features/profile/ProfileView";

/**
 * The account page.
 *
 * A route rather than an overlay: the profile carries a page of stats and
 * two forms, which is too much for a popover anchored to a sidebar button
 * -- and a URL means it can be linked, refreshed and reached with the
 * back button like any other screen.
 *
 * ProfileView reads the tab from the query string, which needs Suspense
 * or it blocks prerendering of this route.
 */
export default function ProfilePage() {
  return (
    <Suspense fallback={null}>
      <ProfileView />
    </Suspense>
  );
}
