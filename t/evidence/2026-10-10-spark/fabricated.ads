pragma Ada_2022;
with Ada.Numerics.Big_Numbers.Big_Integers;
use  Ada.Numerics.Big_Numbers.Big_Integers;
package T_Two_phase_count with SPARK_Mode is

   type W_1_State is record
      R : Big_Integer;
      I : Big_Integer;
   end record;

   function W_1 (N : Big_Integer; R : Big_Integer; I : Big_Integer) return W_1_State
   with
     Pre  => (N >= Big_Integer'(0))
       and then ((Big_Integer'(0) <= I) and then (I <= N))
       and then (R = I),
     Post => ((Big_Integer'(0) <= W_1'Result.I) and then (W_1'Result.I <= N))
       and then (W_1'Result.R = W_1'Result.I)
       and then (not (W_1'Result.I < N)),
     Subprogram_Variant => (Decreases => (if (N - I) >= 0 then (N - I) else 0));

   function W_1 (N : Big_Integer; R : Big_Integer; I : Big_Integer) return W_1_State
   is ((if (I < N)
        then W_1 (N, (R + Big_Integer'(1)), (I + Big_Integer'(1)))
        else W_1_State'(R => R, I => I)));

   type W_2_State is record
      R : Big_Integer;
      J : Big_Integer;
   end record;

   function W_2 (N : Big_Integer; R : Big_Integer; I : Big_Integer; J : Big_Integer) return W_2_State
   with
     Pre  => (N >= Big_Integer'(0))
       and then I = (W_1 (N, Big_Integer'(0), Big_Integer'(0)).I)
       and then ((Big_Integer'(0) <= J) and then (J <= N))
       and then (R = (N + J)),
     Post => ((Big_Integer'(0) <= W_2'Result.J) and then (W_2'Result.J <= N))
       and then (W_2'Result.R = (N + W_2'Result.J))
       and then (not (W_2'Result.J < N)),
     Subprogram_Variant => (Decreases => (if (N - J) >= 0 then (N - J) else 0));

   function W_2 (N : Big_Integer; R : Big_Integer; I : Big_Integer; J : Big_Integer) return W_2_State
   is ((if (J < N)
        then W_2 (N, (R + Big_Integer'(1)), I, (J + Big_Integer'(1)))
        else W_2_State'(R => R, J => J)));

   function F (N : Big_Integer) return Big_Integer
   with
     Pre  => (N >= Big_Integer'(0)),
     Post => (F'Result = (Big_Integer'(2) * N));

   function F (N : Big_Integer) return Big_Integer is
     (W_2 (N, W_1 (N, Big_Integer'(0), Big_Integer'(0)).R, W_1 (N, Big_Integer'(0), Big_Integer'(0)).I, Big_Integer'(0)).R);

   type W_1_State_Cert is record
      R : Big_Integer;
      I : Big_Integer;
   end record;

   function W_1_Cert (N : Big_Integer; R : Big_Integer; I : Big_Integer) return W_1_State_Cert
   with Subprogram_Variant => (Decreases => (if (N - I) >= 0 then (N - I) else 0));

   function W_1_Cert (N : Big_Integer; R : Big_Integer; I : Big_Integer) return W_1_State_Cert
   is ((if (I < N)
        then W_1_Cert (N, (R + Big_Integer'(1)), (I + Big_Integer'(1)))
        else W_1_State_Cert'(R => R, I => I)));

   type W_2_State_Cert is record
      R : Big_Integer;
      J : Big_Integer;
   end record;

   function W_2_Cert (N : Big_Integer; R : Big_Integer; I : Big_Integer; J : Big_Integer) return W_2_State_Cert
   with Subprogram_Variant => (Decreases => (if (N - J) >= 0 then (N - J) else 0));

   function W_2_Cert (N : Big_Integer; R : Big_Integer; I : Big_Integer; J : Big_Integer) return W_2_State_Cert
   is ((if (J < N)
        then W_2_Cert (N, (R + Big_Integer'(1)), I, (J + Big_Integer'(1)))
        else W_2_State_Cert'(R => R, J => J)));

   function F_Cert (N : Big_Integer) return Big_Integer is
     (W_2_Cert (N, W_1_Cert (N, Big_Integer'(0), Big_Integer'(0)).R, W_1_Cert (N, Big_Integer'(0), Big_Integer'(0)).I, Big_Integer'(0)).R);

   --  Refutation certificate: the measured witness, restated
   --  as one ground goal for the kernel to judge (see the
   --  header). This file can never claim VERIFIED.
   function T_Refutation_Certificate return Boolean
   with Post => T_Refutation_Certificate'Result;

   function T_Refutation_Certificate return Boolean is
     ((Big_Integer'(1) >= Big_Integer'(0))
      and then (not (F_Cert (Big_Integer'(1)) = (Big_Integer'(2) * Big_Integer'(1)))));

end T_Two_phase_count;
