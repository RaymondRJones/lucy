# Make Acceptable for Real World Users

None of the pre-screen questions were smart defaulted to the forms,

Also, I'd like the pre-screen questions to have more focused UI like the I-485 form and so on while their being answered so it can naturally move the user to the next set of quetions as they ffinish and doesn't look like a case management UI (remove branch result section / Title section called 'guided ingestion' / Left side section of "Greencard Packet"

The prescreen is connected ot the forms and the brancing logic should flow the user to the next natural point

Once the packet is start and prescreen has begun and ended, it should ask the user which form to start next and give the options from what's next int heir path, then navigat ehtme to the next form. When they finish that form, the form should ask them to generate draft, go to next, or generate ful packet


There's too many "Missing required answers" that visiaully appear, limit them to not display all 121 but just 5

#### Privacy of User Data

Applicaiton is in perfect state, but the current version can be called for debug mode, where all case data is present and available via dropdown.

There should be another run state for production mode, where users must use Clerk to sign in and view their case and only their case.

#### Encrpytion of data

Something that allows encrpytion like Convex or AWS DynamoDB should be used so people SSN and os on isn't presnt

S3 or Cloudflare buckets should be used for sotrage of documents so we aren't just storing everything on the server. 

#### Analytics

It's important to know how many users are actively using the app. Clerk will track logins and we also want to know last time logged in, forms compelted by users, number of full packets generated for each user, and later have a script that can get the conglomerate of this. Then we can display it on the aggregate number of forms and time saved whe new users visit the site

# Sales

Landing page needs improvement, need to call out pain points of niche

Link to Discord / Skool group

# Sales and Conversion (Keep everything free until 10 users, then we will implmenet this later)

Landing page needs improvements to improve sales. The User Flow also needs improvements to optimize conversion and offer upsells
