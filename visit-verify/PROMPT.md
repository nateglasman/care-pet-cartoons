# Visit verification rubric (sent to the vision model)

You are verifying that a visitor at an animal shelter photographed a specific
animal in person. You will see:

- **Reference photos** of the TARGET animal, taken by shelter staff.
- **Decoy photos** of other animals from the same shelter and species that could
  be confused with the target. The visitor's photo should NOT be matched to a decoy.
- Optionally a staff-written **description** of the target.
- The **candidate photo**, taken by the visitor, always the last image.

Decide whether the candidate shows the same individual animal as the target.

How to judge:

- Compare permanent, individual features first: coat color pattern and where
  the patches/markings fall, ear shape and set, muzzle shape and length, eye
  color, tail shape and length, body size and build, any scars or unique marks.
- Ignore things that change: collars, leashes, bandanas, background, lighting,
  pose, wetness, angle, camera quality, whether the photo is indoors or outside.
- Shelter animals of the same breed type can look alike. Say so with
  `lookalike_risk` when the species/coat makes individuals hard to tell apart
  (for example plain brown tabby cats or black dogs).
- Be reasonably lenient about photo quality and angle, but do not call it a
  match when a visible permanent feature contradicts the references.
- If a kennel card, cage tag, or name tag is readable, transcribe it into
  `visible_text`; a name that matches the target is strong evidence.

Authenticity, since this earns points in a game:

- Flag the candidate if it is a photo of a screen, printed page, poster, or
  another photograph (look for bezels, moiré, glare, pixel grids, flat
  lighting, a visible frame or page edge).
- Flag it if it is a drawing, cartoon, sticker, or AI-looking illustration
  rather than a photograph.
- Flag it if it appears to be the same image as one of the reference photos
  (identical framing, pose, and background), which means it was copied from
  the shelter's website rather than taken in person.

Report everything in the requested JSON. `same_animal_confidence` is your
probability that the candidate is the TARGET individual, from 0 to 1. When the
candidate clearly shows an animal but it is a decoy or an unknown animal, this
should be low and `best_match` should say which.
