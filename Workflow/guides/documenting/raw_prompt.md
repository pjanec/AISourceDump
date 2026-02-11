 - Traverse all cs projects you find in thes folder and subfolder.
 - Ignore test and benchmark projects.
 - For each project analyze its source code thoroughly and write a detailed architectural document
   with ascii art block diagrams and description of the purpose, principles, expected usage (with examples),
   best practices, relations to other projects.
 - If there is a readme, take the infomration from it but at the same time check if the source code
   has not diverged and the readme is still up to date (mention this doc up-to-date status in the resulting document).
 - The goal is get a detailed overview of all components. Once all csproj sources are analyzed and documented in details,
   write an overview readme document about the while solution, with links to individual partial documents
   for individual parts. The goal is give an overview of what everything the solution contains.
 - Pay special attantion to the relationship between different component, draw block diagrams and sequence diagrams
   as needed to describe how individual parts cooperate. Feel free to create multiple relationship document if you
   see there are different groups of strong relations - use multipe document to maintain allow for high detail level
   of each.
 - First make a check list of all projects and save it to a file.
 - Remember to look at the checklist to get next unfinished project.
 - During the analysis of individual projects, keep add new check items for relationships between different
   project once you discover some so you can later return back and work on that relation ship document in more
   detail once you process the details of all individual parts.
 - Do not stop until all the items on the checklist (also those added later once you discover some) are marked
   as finished, meaning there is a detailed design documetn existing for it (at least 500 lines each). Update the
   check list after you finish every document.
 - Before you start, write instructions for yourself how to work (based on this prompt) and remeber to return to it
   every time you finish a detailed document for a single csproj so you refresh your memory aboout what is necessary
   to do.
 - Basically your procedure is
     1. read instructions,
     2. look at check list and work on the first not yet finished item
     3. process the item
     4. verify the success condition (document exist, has minimum amount of lines)
     5. mark item as finished
     6. look for next unfinished one and start working on it
     7. keep repeating untill al done.
