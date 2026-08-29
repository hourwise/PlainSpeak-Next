"""Reading documents into text.

Currently every reader flattens its input to a plain string, which is why
the engine cannot yet tell a heading from a quotation or a code block from
prose. Replacing that with a structured representation is the next
architectural step.
"""


