# Measurement and the construct it stands for

The gap between a construct and the instrument used to measure it is not a
technical inconvenience to be minimised; it is a substantive claim about the
world, and treating it as the former is how a literature comes to be organised
around a quantity nobody intended to study.

Consider readability. The construct of interest — whether a reader can understand
a text — is a relation between a document, a person and a purpose. The
instruments in common use are functions of sentence length and word length. That
these instruments correlate with comprehension in the populations on which they
were validated is well established; that they measure comprehension is a
different proposition, and the distance between the two is where most of the
difficulty lies.

## The substitution problem

Once an instrument is convenient, it tends to displace the construct it was
built to approximate. The mechanism is not mysterious. The instrument produces a
number, the number can be compared across documents, and comparison is what
institutions need in order to act. Within a few years the requirement is stated
in terms of the instrument, and the construct has become, at best, a historical
justification for a target.

This substitution is visible in the readability literature in a specific way.
Several widely used formulas were developed for particular populations —
schoolchildren, in the case of at least two of the most cited — and validated
against comprehension tests appropriate to those populations. Applied to adult
technical prose, they continue to produce a number, because arithmetic does not
know what it is describing. Whether that number bears the same relation to
comprehension is an empirical question that is rarely asked, in part because the
formula's output looks equally authoritative in both settings.

The point is not that such measures are useless. It is that a measure carries its
validation context with it, and detaching the measure from that context is a
methodological decision that ought to be argued for rather than made by default.

## Two failure modes

It is worth distinguishing two ways in which an instrument can come apart from
its construct, because they call for different remedies.

In the first, the instrument is systematically biased with respect to some
feature of the material. A readability formula that counts syllables will score
technical vocabulary as difficult regardless of whether the intended audience
knows the terms; a specification written for engineers will therefore be judged
harshly for using the words its readers expect. The remedy here is stratification
— validating separately within the populations and genres of interest — and the
cost is that a single comparable number is no longer available.

In the second, the instrument is manipulable independently of the construct.
Where a formula rewards short sentences, a document can be improved on the
measure by breaking sentences at arbitrary points, producing prose that scores
better and reads worse. This is not a hypothetical: it is the predictable
consequence of optimising against any measure that stands in for something it
does not fully capture, and it is why measures used for evaluation and measures
used for improvement should generally not be the same measures.

The second failure mode is the more serious of the two, since stratification can
in principle address the first, whereas the second is a property of the
relationship between measurement and incentive rather than of the instrument
itself.

## What follows for practice

Several things follow, though none of them amounts to abandoning measurement.

First, a measure should be reported alongside the material it was computed over,
not in place of it. A grade level attached to a document is far less informative
than a grade level attached to a document together with its sentence-length
distribution, since the distribution reveals the artificial shortening that the
summary conceals.

Second, and relatedly, dimensional reporting is preferable to aggregate scoring
wherever the dimensions are themselves interpretable. An aggregate hides the
disagreement between its components; where two components disagree, that
disagreement is usually the most informative thing available, and averaging is
precisely the operation that destroys it.

Third, the population and purpose for which an instrument was validated should
travel with the instrument. This is a documentation practice rather than a
statistical one, but it is the practice whose absence does the most damage,
because a measure whose provenance has been lost cannot be criticised on the
grounds that made it appropriate in the first place.

## An objection

One might object that this line of argument, pressed far enough, licenses no
measurement at all: every instrument approximates its construct, so every
instrument is vulnerable to the substitution problem, and the counsel to attend
to the gap is either trivial or paralysing.

The objection has force, and the response is a matter of degree rather than
kind. What distinguishes a defensible measurement practice from an indefensible
one is not the absence of a gap but the presence of an account of it: whether the
gap has been characterised, whether its likely direction is known, and whether
the uses to which the measure is put are ones the gap does not undermine. A
measure used to flag documents for human review can tolerate a great deal of
imprecision. The same measure used to certify that a document meets a legal
accessibility requirement cannot, and the difference lies in what happens
downstream rather than in the instrument.

## Conclusion

The recommendation, then, is modest but not empty. Instruments should be reported
with their construct, their validation population and their known failure modes
attached; aggregate scores should be avoided where dimensional reporting is
possible; and the uses to which a measure is put should be constrained by the
strength of the evidence linking it to the construct rather than by the
convenience of the number it produces.

None of this is novel as a methodological principle. It is, however, routinely
ignored in practice, and the readability literature offers a well-documented case
of what that neglect produces over several decades: a family of measures in
widespread institutional use, applied far outside the conditions of their
validation, whose outputs are treated as facts about documents rather than as
estimates carrying assumptions.
