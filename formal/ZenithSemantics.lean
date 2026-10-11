import Init

/-
A small contract model for Zenith. A skill is a parameterized relation, not
an assertion that its natural-language instruction implements the relation.
No forecast correctness or language-model behavior is assumed here.
-/
namespace Zenith

universe u v w x

abbrev Skill (Parameters : Type u) (Input : Type v) (Output : Type w) :=
  Parameters → Input → Output → Prop

def compose {P : Type u} {Q : Type v} {A : Type w} {B : Type x} {C : Type}
    (first : Skill P A B) (second : Skill Q B C) : Skill (P × Q) A C :=
  fun params input output => ∃ middle, first params.1 input middle ∧ second params.2 middle output

def Refines {P : Type u} {A : Type v} {B : Type w}
    (candidate reference : Skill P A B) : Prop :=
  ∀ params input output, candidate params input output → reference params input output

def Satisfies {P : Type u} {A : Type v} {B : Type w}
    (skill : Skill P A B) (pre : A → Prop) (post : B → Prop) : Prop :=
  ∀ params input output, pre input → skill params input output → post output

theorem refinement_trans {P : Type u} {A : Type v} {B : Type w}
    {f g h : Skill P A B} (hfg : Refines f g) (hgh : Refines g h) : Refines f h :=
  fun params input output proof => hgh params input output (hfg params input output proof)

theorem composition_refines {P Q A B C : Type}
    {f f' : Skill P A B} {g g' : Skill Q B C}
    (hf : Refines f' f) (hg : Refines g' g) :
    Refines (compose f' g') (compose f g) := by
  intro params input output proof
  obtain ⟨middle, first, second⟩ := proof
  exact ⟨middle, hf _ _ _ first, hg _ _ _ second⟩

theorem composition_contract {P Q A B C : Type}
    {f : Skill P A B} {g : Skill Q B C} {pre : A → Prop} {middle : B → Prop} {post : C → Prop}
    (hf : Satisfies f pre middle) (hg : Satisfies g middle post) :
    Satisfies (compose f g) pre post := by
  intro params input output before proof
  obtain ⟨value, first, second⟩ := proof
  exact hg params.2 value output (hf params.1 input value before first) second

inductive EvidenceClass where
  | subject_side_evidence
  | truth_side_evidence
  deriving DecidableEq, Repr

structure Evidence where
  availableAt : Nat
  contextClass : EvidenceClass
  deriving DecidableEq, Repr

def ForwardSafe (cutoff : Nat) (evidence : Evidence) : Prop :=
  evidence.availableAt ≤ cutoff ∧ evidence.contextClass = .subject_side_evidence

instance (cutoff : Nat) (evidence : Evidence) : Decidable (ForwardSafe cutoff evidence) :=
  inferInstanceAs (Decidable (evidence.availableAt ≤ cutoff ∧ evidence.contextClass = .subject_side_evidence))

def ContextSafe (cutoff : Nat) (context : List Evidence) : Prop :=
  ∀ evidence ∈ context, ForwardSafe cutoff evidence

theorem safe_context_no_future {cutoff : Nat} {context : List Evidence}
    (safe : ContextSafe cutoff context) {evidence : Evidence} (member : evidence ∈ context) :
    evidence.availableAt ≤ cutoff := (safe evidence member).1

theorem safe_context_no_truth {cutoff : Nat} {context : List Evidence}
    (safe : ContextSafe cutoff context) {evidence : Evidence} (member : evidence ∈ context) :
    evidence.contextClass ≠ .truth_side_evidence := by
  have subject := (safe evidence member).2
  intro truth
  rw [subject] at truth
  cases truth

theorem safe_context_append {cutoff : Nat} {left right : List Evidence}
    (hl : ContextSafe cutoff left) (hr : ContextSafe cutoff right) :
    ContextSafe cutoff (left ++ right) := by
  revert hl
  induction left with
  | nil =>
    intro _ evidence member
    exact hr evidence member
  | cons head tail inductionHypothesis =>
    intro hl evidence member
    cases member with
    | head => exact hl _ (.head _)
    | tail _ rest =>
      exact inductionHypothesis (fun evidence member => hl evidence (.tail _ member)) evidence rest

/- A path has at least one edge: acyclicity forbids a nonempty return path. -/
inductive Path {V : Type u} (edge : V → V → Prop) : V → V → Prop where
  | single {a b} : edge a b → Path edge a b
  | extend {a b c} : Path edge a b → edge b c → Path edge a c

def Ranked {V : Type u} (edge : V → V → Prop) (rank : V → Nat) : Prop :=
  ∀ a b, edge a b → rank a < rank b

theorem path_rank_increases {V : Type u} {edge : V → V → Prop} {rank : V → Nat}
    (certificate : Ranked edge rank) {a b} (path : Path edge a b) : rank a < rank b := by
  induction path with
  | single proof => exact certificate _ _ proof
  | extend _ proof previous => exact Nat.lt_trans previous (certificate _ _ proof)

theorem ranked_graph_acyclic {V : Type u} {edge : V → V → Prop} {rank : V → Nat}
    (certificate : Ranked edge rank) (a : V) : ¬ Path edge a a := by
  intro cycle
  exact Nat.lt_irrefl (rank a) (path_rank_increases certificate cycle)

def InsertEdge {V : Type u} (edge : V → V → Prop) (source target : V) : V → V → Prop :=
  fun a b => edge a b ∨ (a = source ∧ b = target)

theorem insert_edge_preserves_rank {V : Type u} {edge : V → V → Prop} {rank : V → Nat}
    (certificate : Ranked edge rank) {source target : V} (forward : rank source < rank target) :
    Ranked (InsertEdge edge source target) rank := by
  intro a b proof
  rcases proof with old | ⟨rfl, rfl⟩
  · exact certificate a b old
  · exact forward

/- An inserted check can have the same externally observed relation as a skill
by filtering outputs with a contract already guaranteed by that skill. -/
def checked {P A B : Type} (skill : Skill P A B) (post : B → Prop) : Skill P A B :=
  fun params input output => skill params input output ∧ post output

theorem checked_refines {P A B : Type} (skill : Skill P A B) (post : B → Prop) :
    Refines (checked skill post) skill := fun _ _ _ proof => proof.1

theorem checked_preserves_when_guaranteed {P A B : Type} {skill : Skill P A B} {post : B → Prop}
    (guarantee : ∀ params input output, skill params input output → post output) :
    Refines skill (checked skill post) := fun params input output proof =>
      ⟨proof, guarantee params input output proof⟩

/- Exact finite checker, consumed by the Python-generated graph instance. -/
def rankChecks {V : Type} (rank : V → Nat) (edges : List (V × V)) : Bool :=
  edges.all (fun edge => decide (rank edge.1 < rank edge.2))

private theorem and_true_elim (a b : Bool) : (a && b) = true → a = true ∧ b = true := by
  cases a <;> cases b <;> decide

theorem rank_checks_sound {V : Type} {rank : V → Nat} {edges : List (V × V)}
    (accepted : rankChecks rank edges = true) :
    Ranked (fun a b => (a, b) ∈ edges) rank := by
  revert accepted
  induction edges with
  | nil =>
    intro _ a b member
    cases member
  | cons head tail inductionHypothesis =>
    intro accepted a b member
    have conjunction : (decide (rank head.1 < rank head.2) && rankChecks rank tail) = true := accepted
    have headAccepted := (and_true_elim _ _ conjunction).1
    have tailAccepted := (and_true_elim _ _ conjunction).2
    cases member with
    | head => exact of_decide_eq_true headAccepted
    | tail _ rest => exact inductionHypothesis tailAccepted a b rest

example : ForwardSafe 10 ⟨9, .subject_side_evidence⟩ := by decide
example : ¬ ForwardSafe 10 ⟨11, .subject_side_evidence⟩ := by decide
example : ¬ ForwardSafe 10 ⟨9, .truth_side_evidence⟩ := by decide
example : rankChecks id [(0, 1), (1, 2)] = true := by decide
example : rankChecks id [(0, 1), (1, 0)] = false := by decide

#print axioms refinement_trans
#print axioms composition_refines
#print axioms composition_contract
#print axioms safe_context_no_future
#print axioms safe_context_no_truth
#print axioms safe_context_append
#print axioms path_rank_increases
#print axioms ranked_graph_acyclic
#print axioms insert_edge_preserves_rank
#print axioms checked_refines
#print axioms checked_preserves_when_guaranteed
#print axioms rank_checks_sound

end Zenith
