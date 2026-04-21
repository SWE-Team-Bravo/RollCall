[1mdiff --git a/pages/4_Flight_Management.py b/pages/4_Flight_Management.py[m
[1mindex e0fcf92..39850eb 100644[m
[1m--- a/pages/4_Flight_Management.py[m
[1m+++ b/pages/4_Flight_Management.py[m
[36m@@ -1,4 +1,5 @@[m
 import streamlit as st[m
[32m+[m[32mfrom utils.st_helpers import confirm_destructive_action[m[41m[m
 [m
 from utils.auth import require_role[m
 from services.cadets import build_cadet_display_map, get_cadets_by_flight[m
[36m@@ -132,7 +133,7 @@[m [melse:[m
                 if c1.button([m
                     "Confirm Delete", key=f"confirm_del_{flight_id}", type="primary"[m
                 ):[m
[31m-                    if confirmation.strip() != "DELETE":[m
[32m+[m[32m                    if not confirm_destructive_action(confirmation):[m[41m[m
                         st.error("Confirmation text does not match 'DELETE'.")[m
                     else:[m
                         unassign_all_cadets_from_flight(flight["_id"])[m
[1mdiff --git a/pages/5_Waivers.py b/pages/5_Waivers.py[m
[1mindex 4e51ad8..eae626a 100644[m
[1m--- a/pages/5_Waivers.py[m
[1m+++ b/pages/5_Waivers.py[m
[36m@@ -1,5 +1,7 @@[m
 import streamlit as st[m
 import pandas as pd[m
[32m+[m[32mfrom utils.st_helpers[m[41m [m
[32m+[m[32mimport confirm_destructive_action, require[m
 [m
 [m
 from services.waivers import ([m
[36m@@ -243,7 +245,7 @@[m [mdef show_waivers([m
             )[m
             c1, c2 = st.columns(2)[m
             if c1.button("Confirm Withdraw", key=f"yes_{waiver_id}", type="primary"):[m
[31m-                if confirmation.strip() != "DELETE":[m
[32m+[m[32m                if not confirm_destructive_action(confirmation):[m
                     st.error("Confirmation text does not match 'DELETE'.")[m
                 else:[m
                     success = withdraw_waiver(selected["_id"])[m
[1mdiff --git a/services/admin_users.py b/services/admin_users.py[m
[1mindex c27aed0..80f1418 100644[m
[1m--- a/services/admin_users.py[m
[1m+++ b/services/admin_users.py[m
[36m@@ -1,4 +1,5 @@[m
 from __future__ import annotations[m
[32m+[m[32mfrom utils.st_helpers import confirm_destructive_action[m
 [m
 from typing import Any, Dict, List, Tuple[m
 [m
[36m@@ -209,5 +210,4 @@[m [mdef confirm_delete_user(confirmation_input: str) -> bool:[m
     "DELETE" (case-insensitive, ignoring surrounding whitespace).[m
     """[m
 [m
[31m-    normalized = (confirmation_input or "").strip().upper()[m
[31m-    return normalized == "DELETE"[m
[32m+[m[32m    return confirm_destructive_action(confirmation_input)[m
[1mdiff --git a/tests/test_admin_users_view.py b/tests/test_admin_users_view.py[m
[1mindex 0e4c722..7d5ee56 100644[m
[1m--- a/tests/test_admin_users_view.py[m
[1m+++ b/tests/test_admin_users_view.py[m
[36m@@ -242,6 +242,8 @@[m [mdef test_build_update_user_payload_removes_waiver_reviewer():[m
 def test_confirm_delete_user_requires_exact_keyword():[m
     # Only the exact keyword (case-insensitive, trimmed) should allow delete.[m
     assert confirm_delete_user("DELETE") is True[m
[31m-    assert confirm_delete_user("  delete  ") is True[m
[32m+[m[32m    assert confirm_delete_user("  DELETE  ") is True[m
[32m+[m[32m    assert confirm_delete_user("delete") is False[m
[32m+[m[32m    assert confirm_delete_user("Delete") is False[m
     assert confirm_delete_user("del") is False[m
     assert confirm_delete_user("DELETE EVERYTHING") is False[m
[1mdiff --git a/utils/st_helpers.py b/utils/st_helpers.py[m
[1mindex 68b8771..ae7812b 100644[m
[1m--- a/utils/st_helpers.py[m
[1m+++ b/utils/st_helpers.py[m
[36m@@ -11,3 +11,7 @@[m [mdef require(val: T | None, message: str) -> T:[m
         st.stop()[m
         raise RuntimeError("Unreachable")[m
     return val[m
[32m+[m
[32m+[m[32mdef confirm_destructive_action(confirmation_input: str) -> bool:[m
[32m+[m[32m    """Return True only when the exact DELETE keyword is entered."""[m
[32m+[m[32m    return (confirmation_input or "").strip() == "DELETE"[m
\ No newline at end of file[m
