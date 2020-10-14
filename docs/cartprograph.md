# Cartprograph

![overview](/docs/images/cartprograph_overview.png)

Cartprograph is for interactively mapping out the state space of a program.

It supports a collaborative view that allows multiple users to simultaneously interact with a program.
In doing so, they build out a tree that represents that state space of the program.
This tree representation allows users to jump around in the state space of the program to continue execution from any previously explored state.
Not only does this mean that users don't have repeat prior interactions to reach that program state, but it also means that they can easily leverage the progress of other users and continue from where they left off.

## The Tree

Cartprograph conveys three levels of abstraction that are present within a program.
1. User-facing Input/Output (IO)
2. Syscalls during execution
3. Basic Blocks during execution

Novice users will find the IO layer most useful.
At this level, they will be able to directly explore the program state space by sending input to the program, and making sense of the output.
More advanced users may be able to get intuitions and an understanding for the program space by analyzing the underlying syscalls and basic blocks explored.

## Legend

In this tree view, we have nodes and edges.

Circular nodes represent the start of the program, and the termination of the program.

Rectangular nodes represent IO.
An IO node encapsulates one or more consecutive read/write syscalls, for read/write syscalls directly relevant to the user's interaction with the program (stdio/tcp).

Edges represent whatever syscalls/basic blocks occur between the IO nodes.

Grey nodes represent standard program start/termination.
Blue nodes represent output.
Yellow nodes represent points where the user may send input.
Green nodes represent previously sent user input.
Purple nodes represent program crashes.

## Information Modal

Users may click on any node or edge to view various bits of information about the state at that point.
User input points (yellow nodes) will need to be double clicked in order to open the modal (or single click if it is already selected).

### IO

![io](/docs/images/cartprograph_io.png)

This tab shows all IO that has occurred at this program state.

### Syscalls

![syscalls](/docs/images/cartprograph_syscalls.png)

This tab shows all syscalls that have occurred during this node/edge.

### Basic Blocks

![basic_blocks](/docs/images/cartprograph_basic_blocks.png)

This tab shows how many basic blocks were traversed during this node/edge.
It also allows users to download a basic block trace that has occurred up to this point (for use external to cartprograph).

### Annotations

![annotations](/docs/images/cartprograph_annotations.png)

Because cartprograph is a collaborative tool, it may be useful to store other bits of data on the node.
Users can communicate their thoughts about this program state.

## Node Score

Each node has some score displayed in the header inside of square braces.
This score indicates how many new basic blocks this node (and prior edge) has explored.
Exploring new basic blocks is crucial to exploring the program's state space.
While reaching new basic blocks is not the only way to explore more of the program's state space, it is certainly a simple and very useful indication of it.
As such, users should seek to generate nodes that result in non-zero scores and also seek to continue exploration from nodes with non-zero scores, as it may indicate being "deeper" in the state space.
Of course, users should also pay close attention to the IO of the program as it may provide semantic insights that may be much more useful than the score.
For instance, it may be necessary to traverse through several zero-score nodes in order to reach a "deeper" state space.

## Example

![explore](/docs/images/cartprograph_explore.png)

The program being explored here is a simple suite of several unix utilities.

To begin interacting, we click on a pending yellow node and start typing.

In the top left node, `ls` is sent to the program. This results in `data`, and other files being listed. We then `cat data` to see its contents, which is returned to the user.

In the top middle node, `rm data` is sent. Then, we perform `cat data` which actually indicates that `No such file exists`. Semantically, we can interpret the IO to understand the differences between the two interaction paths. We can also see from the non-zero score of the output node that we have triggered different basic blocks than the first path's `cat data`.

In the top right node, `exit` is sent. This ultimately terminates the program as indicated by the grey circular node.

## Shortcuts

Moving around the tree can be done with `arrow keys`.
This allows users to quickly move around nodes and edges.
Using `shift` + `arrow keys` will move through several nodes at once.

`Shift backspace` will empty out an input point.

`Enter` on an input point will fork the tree at that program state and send the current input as well as a newline character (text based programs are generally newline delimited).
`ctrl` + `Enter` will send the current input as is without a newline character. This can be useful, for instance, to signify that the user is done interacting (EOF/SHUTDOWN_WR) if done while the current input is empty.
`shift` + `Enter` will insert a newline character (and not send the current input).

## Limitations

Currently, cartprograph will only perform on targets that are deterministic.
If non-determinism is detected, a red desync node will be generated.
If tracing takes too long, the tracer will timeout and a red timeout node will be generated. Unfortunately, the tracer is quite slow currently, and this may occur in programs that need to execute hundreds of thousands of basic blocks. Any other errors will generate a red error node. Backtraces for desyncs and errors will be stored as annotations on their node.

Progress for supporting nondeterminism and significantly increasing tracer speed are currently underway.