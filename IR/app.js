/* =========================================
FILE 3 → app.js
========================================= */

let courses = [];

/* =========================================
LOAD DATASET
========================================= */

fetch('tutorials_clean.json')

.then(response => response.json())

.then(data => {

    courses = data;

    loadDashboard();

    loadEDA();

    createCharts();

});

/* =========================================
PAGE NAVIGATION
========================================= */

function showPage(pageId, btn){

    document.querySelectorAll('.page')

    .forEach(page => {

        page.classList.remove('active-page');
    });

    document.getElementById(pageId)

    .classList.add('active-page');

    document.querySelectorAll('.nav-tab')

    .forEach(tab => {

        tab.classList.remove('active');
    });

    btn.classList.add('active');
}

/* =========================================
DASHBOARD
========================================= */

function loadDashboard(){

    document.getElementById('totalCourses')

    .innerText = courses.length;

    document.getElementById('freeCourses')

    .innerText =
    courses.filter(c => c["Is Free"]).length;

    document.getElementById('certificateCourses')

    .innerText =
    courses.filter(c => c.Certificate).length;

    const avgRating =

        courses.reduce((sum,course)=>{

            return sum + course.Rating;

        },0) / courses.length;

    document.getElementById('avgRating')

    .innerText = avgRating.toFixed(1);

    const categories =

        new Set(courses.map(c=>c.Category));

    document.getElementById('categoriesCount')

    .innerText = categories.size;

    document.getElementById('highlyReviewed')

    .innerText =

    courses.filter(c=>c["Reviews Count"] > 100).length;
}

/* =========================================
EDA
========================================= */

function loadEDA(){

    const avgDuration =

        courses.reduce((sum,course)=>{

            return sum + course.Duration_Hours;

        },0) / courses.length;

    document.getElementById('avgDuration')

    .innerText = avgDuration.toFixed(1);

    const tags = new Set();

    courses.forEach(course=>{

        if(course.Tags){

            course.Tags.forEach(tag=>{

                tags.add(tag);
            });
        }
    });

    document.getElementById('uniqueTags')

    .innerText = tags.size;

    const maxReviews =

        Math.max(...courses.map(c=>c["Reviews Count"]));

    document.getElementById('maxReviews')

    .innerText = maxReviews;

    const topRated =

        Math.max(...courses.map(c=>c.Rating));

    document.getElementById('topRated')

    .innerText = topRated;

    document.getElementById('contentRich')

    .innerText =

    courses.filter(c=>c.Tag_Count > 15).length;

    document.getElementById('longCourses')

    .innerText =

    courses.filter(c=>c.Duration_Hours > 40).length;
}

/* =========================================
CHARTS
========================================= */

function createCharts(){

    createCategoryChart();

    createLevelChart();

    createFreePaidChart();

    createRatingChart();

    createDurationChart();

    createReviewsChart();
}

/* =========================================
CATEGORY CHART
========================================= */

function createCategoryChart(){

    const counts = {};

    courses.forEach(course=>{

        counts[course.Category] =

        (counts[course.Category] || 0) + 1;
    });

    new Chart(

        document.getElementById('categoryChart'),

        {
            type:'bar',

            data:{

                labels:Object.keys(counts),

                datasets:[{

                    data:Object.values(counts)
                }]
            }
        }
    );
}

/* =========================================
LEVEL CHART
========================================= */

function createLevelChart(){

    const counts = {};

    courses.forEach(course=>{

        counts[course.Level] =

        (counts[course.Level] || 0) + 1;
    });

    new Chart(

        document.getElementById('levelChart'),

        {
            type:'pie',

            data:{

                labels:Object.keys(counts),

                datasets:[{

                    data:Object.values(counts)
                }]
            }
        }
    );
}

/* =========================================
FREE VS PAID
========================================= */

function createFreePaidChart(){

    const free =

    courses.filter(c=>c["Is Free"]).length;

    const paid = courses.length - free;

    new Chart(

        document.getElementById('freePaidChart'),

        {
            type:'doughnut',

            data:{

                labels:['Free','Paid'],

                datasets:[{

                    data:[free,paid]
                }]
            }
        }
    );
}

/* =========================================
RATING DISTRIBUTION
========================================= */

function createRatingChart(){

    const buckets = [0,0,0,0,0];

    courses.forEach(course=>{

        const rating = Math.floor(course.Rating);

        if(rating >=0 && rating <5){

            buckets[rating]++;
        }
    });

    new Chart(

        document.getElementById('ratingChart'),

        {
            type:'bar',

            data:{

                labels:['0-1','1-2','2-3','3-4','4-5'],

                datasets:[{

                    data:buckets
                }]
            }
        }
    );
}

/* =========================================
DURATION CHART
========================================= */

function createDurationChart(){

    new Chart(

        document.getElementById('durationChart'),

        {
            type:'line',

            data:{

                labels:
                courses.map((c,i)=>i+1),

                datasets:[{

                    data:
                    courses.map(c=>c.Duration_Hours)
                }]
            }
        }
    );
}

/* =========================================
REVIEWS CHART
========================================= */

function createReviewsChart(){

    const sorted =

    [...courses]

    .sort((a,b)=>

        b["Reviews Count"] -
        a["Reviews Count"]

    )

    .slice(0,10);

    new Chart(

        document.getElementById('reviewsChart'),

        {
            type:'bar',

            data:{

                labels:
                sorted.map(c=>c.Title),

                datasets:[{

                    data:
                    sorted.map(c=>c["Reviews Count"])
                }]
            }
        }
    );
}

/* =========================================
AI RECOMMENDER (FIXED VERSION)
========================================= */

function generateRecommendations(){

    const level =
        document.getElementById('levelInput')
        .value
        .trim()
        .toLowerCase();

    const category =
        document.getElementById('categoryInput')
        .value
        .trim()
        .toLowerCase();

    const isFree =
        document.getElementById('priceInput')
        .value;

    const certificate =
        document.getElementById('certificateInput')
        .value;

    const keywords =
        document.getElementById('keywordInput')
        .value
        .toLowerCase()
        .split(',')
        .map(k => k.trim())
        .filter(k => k !== "");

    const maxDuration =
        parseFloat(
            document.getElementById('durationInput')
            .value
        );

    /* =========================================
    FILTER COURSES FIRST
    ========================================= */

    let filteredCourses = courses.filter(course => {

        /* =========================================
        STRICT LEVEL FILTER
        ========================================= */

        if(level){

            const courseLevel =
                course.Level
                .trim()
                .toLowerCase();

            if(courseLevel !== level){

                return false;
            }
        }

        /* =========================================
        CATEGORY FILTER
        ========================================= */

        if(category){

            const courseCategory =
                course.Category
                .trim()
                .toLowerCase();

            if(!courseCategory.includes(category)){

                return false;
            }
        }

        /* =========================================
        FREE / PAID FILTER
        ========================================= */

        if(isFree !== ""){

            if(
                course["Is Free"].toString()
                !== isFree
            ){

                return false;
            }
        }

        /* =========================================
        CERTIFICATE FILTER
        ========================================= */

        if(certificate !== ""){

            if(
                course.Certificate.toString()
                !== certificate
            ){

                return false;
            }
        }

        /* =========================================
        STRICT MAX DURATION FILTER
        ========================================= */

        if(!isNaN(maxDuration)){

            if(course.Duration_Hours > maxDuration){

                return false;
            }
        }

        return true;
    });

    /* =========================================
    AI SCORING
    ========================================= */

    const scored = filteredCourses.map(course => {

        let score = 0;

        /* =========================================
        KEYWORD MATCH SCORE
        ========================================= */
        /* =========================================
ADVANCED KEYWORD MATCHING
        ========================================= */

        let keywordScore = 0;

        const searchableText = `

        ${course.Title || ""}

        ${course.Description || ""}

        ${course["Short Description"] || ""}

        ${course.Category || ""}

        ${(course.Tags || []).join(" ")}

        ${(course["Learning Outcomes"] || []).join(" ")}

        `
        .toLowerCase();

       keywords.forEach(keyword => {

    if(keyword.length === 0) return;

            /*
            Exact keyword occurrence count
            */

            const matches =
                searchableText.match(
                    new RegExp(keyword, "g")
                );

            if(matches){

                /*
                Stronger scoring
                */

                keywordScore += matches.length * 40;
            }
        });

        /* =========================================
        FINAL KEYWORD SCORE
        ========================================= */

        score += keywordScore;

        /* =========================================
        RATING SCORE
        ========================================= */

        score += course.Rating * 5;

        /* =========================================
        DURATION PRIORITY
        Higher score when closer to max duration
        ========================================= */

        if(!isNaN(maxDuration)){

            const difference =
                Math.abs(
                    maxDuration -
                    course.Duration_Hours
                );

            score += (100 - difference);
        }

        /* =========================================
        REVIEW SCORE
        ========================================= */

        score += course["Reviews Count"] * 0.1;

        return {

            ...course,

            ai_score: score.toFixed(2)
        };

    });

    /* =========================================
    SORT DESCENDING
    ========================================= */

    scored.sort((a,b) => {

        return b.ai_score - a.ai_score;
    });

    /* =========================================
    TOP 5
    ========================================= */

    const top5 = scored.slice(0,5);

    renderRecommendations(top5);
}
/* =========================================
RENDER RESULTS
========================================= */

function renderRecommendations(results){

    const container =

        document.getElementById(
            'recommendationResults'
        );

    container.innerHTML = '';

    results.forEach(course=>{

        container.innerHTML += `

        <div class="result-card">

            <h2>${course.Title}</h2>

            <p>
                <b>Category:</b>
                ${course.Category}
            </p>

            <p>
                <b>Level:</b>
                ${course.Level}
            </p>

            <p>
                <b>Rating:</b>
                ${course.Rating}
            </p>

            <p>
                <b>Duration:</b>
                ${course.Duration_Hours} Hours
            </p>

            <p>
                <b>AI Score:</b>
                ${course.ai_score}
            </p>

            <a href="${course.URL}"
               target="_blank">

               Open Course

            </a>

        </div>
        `;
    });
}