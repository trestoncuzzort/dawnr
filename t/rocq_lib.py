#!/usr/bin/env python3
"""rocq_lib.py: SPEC.md "The library (v1)", "Reductions (v1)" and "Higher-order calls (v1)" in the Rocq lowering
(PREDICT T10, 2026-10-06; internal/RESEARCH-2026-10-06-landscape.md decision D1).

The Rocq column encodes a sequence as a function `Z -> Z` with a length (lower_rocq.py's own encoding), so the
library is written over that pair: `min`, `max`, `abs`, `gcd`, `pow`, `isqrt` are the stdlib's own `Z` functions
(`lia` reads min/max/abs itself; gcd's sign and isqrt's bounds are stated as facts at each use); `sum`, membership,
max/min of one argument, `any`/`all` and the higher-order calls are fuel `Fixpoint`s over `Z.to_nat` of the length,
recursing from the end, so a prefix's value is one unfolding from the next (the shape a loop invariant reaches);
`rev` is `fun k => f (n - 1 - k)`; `sort` is a stable insertion sort over the listed elements, read back as a
function. Every definition is transparent, so a ground certificate reduces by computation. Measured first on two
hand probes (scratch p1.v, p2.v, 2026-10-06): every lemma below closed under the global context."""
from __future__ import annotations

# the library ops this column carries ("in" is membership in a seq, "maxs" max/min of one argument)
ROCQ_LIB = frozenset({"min", "max", "abs", "gcd", "pow", "isqrt", "sum", "rev", "sort", "maxs", "in",
                      "any", "all"})

_TEXT: dict[str, str] = {}

_TEXT["sum"] = r"""(* SPEC.md "The library (v1)": sum, over the first n elements, recursing from the end *)
Fixpoint t_sum_nat (m : nat) (f : Z -> Z) : Z :=
  match m with
  | O => 0
  | S m' => t_sum_nat m' f + f (Z.of_nat m')
  end.
Definition t_sum (f : Z -> Z) (n : Z) : Z := t_sum_nat (Z.to_nat n) f.

Lemma t_sum_one : forall f, t_sum f 1 = f 0.
Proof. intros f. reflexivity. Qed.

Lemma t_sum_step : forall f i, 0 <= i -> t_sum f (i + 1) = t_sum f i + f i.
Proof.
  intros f i Hi. unfold t_sum. replace (Z.to_nat (i + 1)) with (S (Z.to_nat i)) by lia.
  cbn [t_sum_nat]. rewrite Z2Nat.id by lia. reflexivity.
Qed.

Lemma t_sum_app : forall f g n m, 0 <= n -> 0 <= m ->
  t_sum (t_app f g n) (n + m) = t_sum f n + t_sum g m.
Proof.
  intros f g n m Hn Hm. unfold t_app.
  assert (Hp : forall j, (j <= Z.to_nat n)%nat ->
    t_sum_nat j (fun k => if k <? n then f k else g (k - n)) = t_sum_nat j f).
  { induction j as [| j IH]; intros Hj; cbn [t_sum_nat]; [reflexivity |].
    rewrite IH by lia. replace (Z.of_nat j <? n) with true by (symmetry; apply Z.ltb_lt; lia). reflexivity. }
  assert (Hs : forall j, t_sum_nat (Z.to_nat n + j) (fun k => if k <? n then f k else g (k - n))
                         = t_sum_nat (Z.to_nat n) f + t_sum_nat j g).
  { induction j as [| j IH].
    - rewrite Nat.add_0_r. rewrite Hp by lia. cbn [t_sum_nat]. lia.
    - rewrite Nat.add_succ_r. cbn [t_sum_nat]. rewrite IH.
      replace (Z.of_nat (Z.to_nat n + j) <? n) with false by (symmetry; apply Z.ltb_ge; lia).
      replace (Z.of_nat (Z.to_nat n + j) - n) with (Z.of_nat j) by lia. lia. }
  unfold t_sum. replace (Z.to_nat (n + m)) with (Z.to_nat n + Z.to_nat m)%nat by lia. apply Hs.
Qed.
"""

_TEXT["in"] = r"""(* SPEC.md "The library (v1)": membership in a seq, decided over the first n elements *)
Fixpoint t_memb_nat (m : nat) (f : Z -> Z) (x : Z) : bool :=
  match m with
  | O => false
  | S m' => orb (t_memb_nat m' f x) (Z.eqb (f (Z.of_nat m')) x)
  end.
Definition t_memb (f : Z -> Z) (n : Z) (x : Z) : bool := t_memb_nat (Z.to_nat n) f x.

Lemma t_memb_nat_spec : forall m f x,
  t_memb_nat m f x = true <-> exists k, 0 <= k < Z.of_nat m /\ f k = x.
Proof.
  induction m as [| m' IH]; intros f x; cbn [t_memb_nat].
  - split; [discriminate | intros [k [Hk _]]; lia].
  - rewrite Bool.orb_true_iff, IH, Z.eqb_eq. split.
    + intros [[k [Hk Hf]] | H]; [exists k; split; [lia | exact Hf] | exists (Z.of_nat m'); split; [lia | exact H]].
    + intros [k [Hk Hf]].
      destruct (Z.eq_dec k (Z.of_nat m')) as [E | E].
      * right; subst k; exact Hf.
      * left; exists k; split; [lia | exact Hf].
Qed.

Lemma t_memb_spec : forall f n x, 0 <= n ->
  t_memb f n x = true <-> exists k, 0 <= k < n /\ f k = x.
Proof.
  intros f n x Hn. unfold t_memb. rewrite t_memb_nat_spec. rewrite Z2Nat.id by lia. tauto.
Qed.
"""

_TEXT["maxs"] = r"""(* SPEC.md "Reductions (v1)": max(s)/min(s) of one argument, defined on a non-empty seq *)
Fixpoint t_maxs_nat (m : nat) (f : Z -> Z) : Z :=
  match m with
  | O => 0
  | S O => f 0
  | S m' => Z.max (t_maxs_nat m' f) (f (Z.of_nat m'))
  end.
Definition t_maxs (f : Z -> Z) (n : Z) : Z := t_maxs_nat (Z.to_nat n) f.
Fixpoint t_mins_nat (m : nat) (f : Z -> Z) : Z :=
  match m with
  | O => 0
  | S O => f 0
  | S m' => Z.min (t_mins_nat m' f) (f (Z.of_nat m'))
  end.
Definition t_mins (f : Z -> Z) (n : Z) : Z := t_mins_nat (Z.to_nat n) f.

Lemma t_maxs_nat_spec : forall m f, (1 <= m)%nat ->
  (exists k, 0 <= k < Z.of_nat m /\ f k = t_maxs_nat m f) /\
  (forall k, 0 <= k < Z.of_nat m -> f k <= t_maxs_nat m f).
Proof.
  induction m as [| m' IH]; intros f Hm; [lia |].
  destruct m' as [| m''].
  - cbn [t_maxs_nat]. split; [exists 0; split; [lia | reflexivity] | intros k Hk; assert (k = 0) by lia; subst; lia].
  - destruct (IH f ltac:(lia)) as [[k0 [Hk0 Hf0]] Hb].
    change (t_maxs_nat (S (S m'')) f) with (Z.max (t_maxs_nat (S m'') f) (f (Z.of_nat (S m'')))).
    split.
    + destruct (Z.max_spec (t_maxs_nat (S m'') f) (f (Z.of_nat (S m'')))) as [[_ E] | [_ E]]; rewrite E.
      * exists (Z.of_nat (S m'')); split; [lia | reflexivity].
      * exists k0; split; [lia | exact Hf0].
    + intros k Hk.
      destruct (Z.eq_dec k (Z.of_nat (S m''))) as [E | E].
      * subst k; lia.
      * specialize (Hb k ltac:(lia)); lia.
Qed.

Lemma t_mins_nat_spec : forall m f, (1 <= m)%nat ->
  (exists k, 0 <= k < Z.of_nat m /\ f k = t_mins_nat m f) /\
  (forall k, 0 <= k < Z.of_nat m -> t_mins_nat m f <= f k).
Proof.
  induction m as [| m' IH]; intros f Hm; [lia |].
  destruct m' as [| m''].
  - cbn [t_mins_nat]. split; [exists 0; split; [lia | reflexivity] | intros k Hk; assert (k = 0) by lia; subst; lia].
  - destruct (IH f ltac:(lia)) as [[k0 [Hk0 Hf0]] Hb].
    change (t_mins_nat (S (S m'')) f) with (Z.min (t_mins_nat (S m'') f) (f (Z.of_nat (S m'')))).
    split.
    + destruct (Z.min_spec (t_mins_nat (S m'') f) (f (Z.of_nat (S m'')))) as [[_ E] | [_ E]]; rewrite E.
      * exists k0; split; [lia | exact Hf0].
      * exists (Z.of_nat (S m'')); split; [lia | reflexivity].
    + intros k Hk.
      destruct (Z.eq_dec k (Z.of_nat (S m''))) as [E | E].
      * subst k; lia.
      * specialize (Hb k ltac:(lia)); lia.
Qed.

Lemma t_maxs_fact : forall f n, 0 < n ->
  (exists k, 0 <= k < n /\ f k = t_maxs f n) /\ (forall k, 0 <= k < n -> f k <= t_maxs f n).
Proof.
  intros f n Hn. unfold t_maxs.
  destruct (t_maxs_nat_spec (Z.to_nat n) f ltac:(lia)) as [A B].
  rewrite Z2Nat.id in A, B by lia. split; assumption.
Qed.

Lemma t_mins_fact : forall f n, 0 < n ->
  (exists k, 0 <= k < n /\ f k = t_mins f n) /\ (forall k, 0 <= k < n -> t_mins f n <= f k).
Proof.
  intros f n Hn. unfold t_mins.
  destruct (t_mins_nat_spec (Z.to_nat n) f ltac:(lia)) as [A B].
  rewrite Z2Nat.id in A, B by lia. split; assumption.
Qed.
"""

_TEXT["anyall"] = r"""(* SPEC.md "Reductions (v1)": all/any over a predicate on the first n indices *)
Fixpoint t_all_nat (m : nat) (p : Z -> bool) : bool :=
  match m with
  | O => true
  | S m' => t_all_nat m' p && p (Z.of_nat m')
  end.
Fixpoint t_any_nat (m : nat) (p : Z -> bool) : bool :=
  match m with
  | O => false
  | S m' => t_any_nat m' p || p (Z.of_nat m')
  end.
Definition t_all (n : Z) (p : Z -> bool) : bool := t_all_nat (Z.to_nat n) p.
Definition t_any (n : Z) (p : Z -> bool) : bool := t_any_nat (Z.to_nat n) p.

Lemma t_all_nat_spec : forall m p, t_all_nat m p = true <-> (forall k, 0 <= k < Z.of_nat m -> p k = true).
Proof.
  induction m as [| m' IH]; intros p; cbn [t_all_nat].
  - split; [intros _ k Hk; lia | reflexivity].
  - rewrite Bool.andb_true_iff, IH. split.
    + intros [H1 H2] k Hk. destruct (Z.eq_dec k (Z.of_nat m')) as [E | E]; [subst; exact H2 | apply H1; lia].
    + intros H. split; [intros k Hk; apply H; lia | apply H; lia].
Qed.

Lemma t_any_nat_spec : forall m p, t_any_nat m p = true <-> (exists k, 0 <= k < Z.of_nat m /\ p k = true).
Proof.
  induction m as [| m' IH]; intros p; cbn [t_any_nat].
  - split; [discriminate | intros [k [Hk _]]; lia].
  - rewrite Bool.orb_true_iff, IH. split.
    + intros [[k [Hk H]] | H]; [exists k; split; [lia | exact H] | exists (Z.of_nat m'); split; [lia | exact H]].
    + intros [k [Hk H]]. destruct (Z.eq_dec k (Z.of_nat m')) as [E | E];
        [right; subst; exact H | left; exists k; split; [lia | exact H]].
Qed.

Lemma t_all_spec : forall n p, 0 <= n -> t_all n p = true <-> (forall k, 0 <= k < n -> p k = true).
Proof. intros n p Hn. unfold t_all. rewrite t_all_nat_spec, Z2Nat.id by lia. tauto. Qed.

Lemma t_any_spec : forall n p, 0 <= n -> t_any n p = true <-> (exists k, 0 <= k < n /\ p k = true).
Proof. intros n p Hn. unfold t_any. rewrite t_any_nat_spec, Z2Nat.id by lia. tauto. Qed.
"""

_TEXT["rev"] = r"""(* SPEC.md "The library (v1)": rev, the same length, read from the other end *)
Definition t_rev (f : Z -> Z) (n : Z) : Z -> Z := fun k => f (n - 1 - k).
"""

_TEXT["sort"] = r"""(* SPEC.md "Sorting (v1)": a stable insertion sort over the listed elements, read back as a function *)
Fixpoint t_ins (x : Z) (l : list Z) : list Z :=
  match l with
  | nil => x :: nil
  | y :: ys => if x <=? y then x :: y :: ys else y :: t_ins x ys
  end.
Fixpoint t_isort (l : list Z) : list Z :=
  match l with
  | nil => nil
  | x :: xs => t_ins x (t_isort xs)
  end.
Fixpoint t_list_nat (m : nat) (f : Z -> Z) : list Z :=
  match m with
  | O => nil
  | S m' => t_list_nat m' f ++ (f (Z.of_nat m') :: nil)
  end.
Definition t_sortf (f : Z -> Z) (n : Z) : Z -> Z :=
  fun k => nth (Z.to_nat k) (t_isort (t_list_nat (Z.to_nat n) f)) 0.

Lemma t_ins_length : forall x l, length (t_ins x l) = S (length l).
Proof. intros x l. induction l as [| y ys IH]; cbn [t_ins]; [reflexivity |]. destruct (x <=? y); cbn; lia. Qed.

Lemma t_isort_length : forall l, length (t_isort l) = length l.
Proof. induction l as [| x xs IH]; cbn [t_isort]; [reflexivity |]. rewrite t_ins_length, IH. reflexivity. Qed.

Lemma t_list_nat_length : forall m f, length (t_list_nat m f) = m.
Proof. induction m as [| m' IH]; intros f; cbn [t_list_nat]; [reflexivity |]. rewrite length_app, IH. cbn. lia. Qed.

Lemma t_ins_sorted : forall x l, Sorted Z.le l -> Sorted Z.le (t_ins x l).
Proof.
  intros x l H. induction H as [| y ys Hs IH Hhd]; cbn [t_ins].
  - constructor; [constructor | constructor].
  - destruct (Z.leb_spec x y) as [E | E].
    + constructor; [constructor; assumption | constructor; lia].
    + constructor; [exact IH |].
      destruct ys as [| z zs]; cbn [t_ins].
      * constructor; lia.
      * inversion Hhd; subst. destruct (x <=? z); constructor; lia.
Qed.

Lemma t_isort_sorted : forall l, Sorted Z.le (t_isort l).
Proof. induction l as [| x xs IH]; cbn [t_isort]; [constructor | apply t_ins_sorted; exact IH]. Qed.

Lemma t_sortf_le : forall f n i j, 0 <= i -> i <= j -> j < n ->
  t_sortf f n i <= t_sortf f n j.
Proof.
  intros f n i j Hi Hij Hj. unfold t_sortf.
  pose proof (t_isort_sorted (t_list_nat (Z.to_nat n) f)) as Hs.
  apply Sorted_StronglySorted in Hs; [| intros a b c; lia].
  assert (Hl : length (t_isort (t_list_nat (Z.to_nat n) f)) = Z.to_nat n)
    by (rewrite t_isort_length, t_list_nat_length; reflexivity).
  remember (t_isort (t_list_nat (Z.to_nat n) f)) as l eqn:El. clear El.
  assert (Hgen : forall l, StronglySorted Z.le l -> forall a b, (a <= b < length l)%nat -> nth a l 0 <= nth b l 0).
  { clear. induction l as [| x xs IH]; intros Hss a b Hab; [cbn in Hab; lia |].
    inversion Hss as [| ? ? Hss' Hfa]; subst.
    destruct a as [| a'], b as [| b']; cbn [nth]; try lia.
    - rewrite Forall_forall in Hfa. apply Hfa. apply nth_In. cbn in Hab. lia.
    - apply IH; [exact Hss' | cbn in Hab; lia]. }
  apply Hgen; [exact Hs | lia].
Qed.
"""

_ORDER = ["sum", "in", "maxs", "anyall", "rev", "sort"]


def used(x) -> set:
    """The library pieces a task part needs: "maxs" for max/min of one argument, "anyall" for any/all."""
    out: set = set()

    def walk(y):
        if isinstance(y, dict):
            op = y.get("op")
            if op in ("min", "max") and len(y.get("args", [])) == 1:
                out.add("maxs")
            elif op in ("sum", "rev", "sort"):
                out.add(op)
            elif op == "in":
                out.add("in")
            elif op in ("any", "all"):
                out.add("anyall")
            for v in y.values():
                walk(v)
        elif isinstance(y, list):
            for v in y:
                walk(v)
    walk(x)
    return out


def prelude(pieces: set) -> str:
    """The prelude text for the pieces used, in a fixed order (Sorted from the stdlib's Sorting when sort is)."""
    text = [_TEXT[p] for p in _ORDER if p in pieces]
    if not text:
        return ""
    head = ("From Stdlib Require Import Sorting.Sorted.\n" if "sort" in pieces else "")
    return head + "\n".join(text)
